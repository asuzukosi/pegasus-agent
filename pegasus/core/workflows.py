import os
from llm_call import IntelligenceEngine
from xml_processor import XMLProcessor
from utils.logger import logger
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List
from dataclasses import dataclass
import xmltodict


class ChainWorkflow:
    def __init__(self, prompts: list[str], system_prompt: str = ""):
        self.prompts = prompts
        self.engine = IntelligenceEngine(api_key=os.getenv("ANTHROPIC_API_KEY"), 
                                system_prompt=system_prompt)
    
    def run(self, query: str) -> str:
        result = query
        
        for i, prompt in enumerate(self.prompts, start=1):
            logger.info(f"Running prompt {i} of {len(self.prompts)}")
            logger.info(f"Prompt: {prompt}")
            result = self.engine.call(result)
            logger.info(f"Result: {result[:100]}...")
            logger.info(f"--------------------------------")
        return result


class ParallelWorkflow:
    def __init__(self, instruction: str, system_prompt: str = "", num_threads: int = 10):
        self.instruction = instruction
        self.engine = IntelligenceEngine(api_key=os.getenv("ANTHROPIC_API_KEY"), 
                                system_prompt=system_prompt)
        self.num_threads = num_threads
    
    def run(self, inputs: list[str]) -> list[str]:
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = [executor.submit(self.engine.call, f"{self.instruction}<input>{x}</input>") for x in inputs]
            results = [future.result() for future in futures]
        return results

Route = Dict[str, str]

class RoutingWorkflow:
    def __init__(self, selection_prompt: str, routes: List[Route], 
                system_prompt: str = "", num_threads: int = 10):
        self.selection_prompt = selection_prompt
        self.routes = routes
        self.engine = IntelligenceEngine(api_key=os.getenv("ANTHROPIC_API_KEY"), 
                                system_prompt=system_prompt)
        self.num_threads = num_threads

    def _select_route(self, query: str) -> str:
        response = self.engine.call(f"{self.selection_prompt}<options>{self.routes.keys()}</options><query>{query}</query>")
        return response
    
    def _execute_route(self, route: str, query: str) -> str:
        prompt = self.routes[route]
        return self.engine.call(f"{prompt}<query>{query}</query>")


    def run(self, query: str) -> str:
        route = self._select_route(query)
        return self._execute_route(route, query)

@dataclass
class EvaluatorGenerateResult:
    result: str
    thoughts: str
    context: str

@dataclass
class EvaluatorEvaluateResult:
    evaluation: bool
    feedback: str


class OptimizerResult:
    result: str
    chain_of_thought: list[dict]
    memory: list[str]

POSITIVE_EVALUATION_VALUES = ["true", "1", "yes", "pass"]

class EvaluatorOptimizerWorkflow:
    def __init__(self, 
        generate_prompt: str,
        evaluate_prompt: str,
        max_iterations: int = 10,
        system_prompt: str = "",
    ):
        self.generate_prompt = generate_prompt
        self.evaluate_prompt = evaluate_prompt
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.engine = IntelligenceEngine(api_key=os.getenv("ANTHROPIC_API_KEY"), 
                                system_prompt=system_prompt)

    def _generate(self, query: str, context: str=None) -> EvaluatorGenerateResult:
        full_prompt = f"<instruction>{self.generate_prompt}</instruction>"
        if context:
            full_prompt += f"<context>{context}</context>"
        if query:
            full_prompt += f"<query>{query}</query>"
        response = self.engine.call(full_prompt)
        result = XMLProcessor.extract_data(response, "result")
        thoughts = XMLProcessor.extract_data(response, "thoughts")
        return EvaluatorGenerateResult(result=result, 
                                        thoughts=thoughts, 
                                        context=context)

    def _evaluate(self, response: str, query: str) -> EvaluatorEvaluateResult:
        full_prompt = f"<instruction>{self.evaluate_prompt}</instruction>"
        if query:
            full_prompt += f"<reference_query>{query}</reference_query>"
        if response:
            full_prompt += f"<reference_response>{response}</reference_response>"
        response = self.engine.call(full_prompt)
        evaluation = str(XMLProcessor.extract_data(response, "evaluation")).lower()
        evaluation = evaluation in POSITIVE_EVALUATION_VALUES
        feedback = XMLProcessor.extract_data(response, "feedback")
        return EvaluatorEvaluateResult(evaluation=evaluation, 
                                        feedback=feedback)

    def run(self, query: str) -> OptimizerResult:
        memory = []
        chain_of_thought = []

        generate_result: EvaluatorGenerateResult = self._generate(query)
        memory.append(generate_result.result)
        chain_of_thought.append({"thoughts": generate_result.thoughts, 
                                 "result": generate_result.result})
        while len(memory) < self.max_iterations:
            evaluate_result: EvaluatorEvaluateResult = self._evaluate(memory[-1], query)
            if evaluate_result.evaluation:
                return OptimizerResult(result=memory[-1], 
                                        chain_of_thought=chain_of_thought, 
                                        memory=memory)
            else:
                previous_responses = "\n".join([f"<previous_response>{mem}</previous_response>" for mem in memory])
                context = "<previous_responses>" + previous_responses + "</previous_responses>"
                context += "feedback" + evaluate_result.feedback + "</feedback>"

                generate_result: EvaluatorGenerateResult = self._generate(query, context)
                memory.append(generate_result.result)
                chain_of_thought.append({"thoughts": generate_result.thoughts, 
                                        "result": generate_result.result})
        return OptimizerResult(result=memory[-1], 
                                chain_of_thought=chain_of_thought, 
                                memory=memory)

@dataclass
class Task:
    name: str
    description: str
    type: str

@dataclass
class WorkerResult:
    name: str
    description: str
    type: str
    result: str

@dataclass
class DynamicOrchestratorResult:
    results: list[WorkerResult]
    analysis: list[dict]

class DynamicOrchestratorWorkflow:
    def __init__(self, system_prompt: str, 
                orchestrator_prompt: str,
                worker_prompt: str):
        self.engine = IntelligenceEngine(api_key=os.getenv("ANTHROPIC_API_KEY"), 
                                system_prompt=system_prompt)
        self.orchestrator_prompt = orchestrator_prompt
        self.worker_prompt = worker_prompt

    def _get_tasks(self, xml_data: str) -> list[Task]:
        json = xmltodict.parse(xml_data)
        tasks = []
        for task in json["tasks"]["task"]:
            tasks.append(Task(name=task["name"], 
                              description=task["description"], 
                              type=task["type"]))
        return tasks

    def _run_worker(self, task: Task) -> WorkerResult:
        worker_prompt = self._format_prompt(self.worker_prompt, task=task)
        
        response = self.engine.call(worker_prompt)
        result = XMLProcessor.extract_data(response, "result")
        return WorkerResult(name=task.name, 
                            description=task.description, 
                            type=task.type, 
                            result=result)


    def _format_prompt(self, prompt: str, **kwargs) -> str:
        return prompt.format(**kwargs)

    def run(self, query: str) -> DynamicOrchestratorResult:
        orchestrator_prompt = self._format_prompt(self.orchestrator_prompt, query=query)
        response = self.engine.call(orchestrator_prompt)
        tasks_xml = XMLProcessor.extract_data(response, "tasks")
        analysis = XMLProcessor.extract_data(response, "analysis")
        tasks = self._get_tasks(tasks_xml)

        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = [executor.submit(self._run_worker, task) for task in tasks]
            results = [future.result() for future in futures]

        return DynamicOrchestratorResult(results=results, 
                                        analysis=analysis)
