import anthropic
from pydantic import BaseModel
from typing import List


class ResponseContent(BaseModel):
    type: str
    text: str

class EngineResponseStub(BaseModel):
    content: List[ResponseContent]

class IntelligenceEngine:
    def __init__(self, api_key: str, 
                 model: str = "claude-3-5-sonnet-20240620", 
                 system_prompt: str = ""):
        self.api_key = api_key
        self.client = anthropic.Anthropic(api_key=api_key)
        self.system_prompt = system_prompt
        self.model = model

    def call(self, prompt: str) -> str:
        response: EngineResponseStub = self.client.messages.create(
            model=self.model,
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text