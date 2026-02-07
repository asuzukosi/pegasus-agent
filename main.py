from src.client.llm_client import LLMClient
import asyncio

async def main() -> None:
    llm_client = LLMClient()
    response = await llm_client.chat_completion(messages=[{"role": "user", "content": "Hello, how are you?"}], stream=False)
    print(response)

if __name__ == "__main__":
    asyncio.run(main())