from abc import ABC, abstractmethod
import httpx
from src.shared.config import settings


class LLMClient(ABC):
    @abstractmethod
    async def chat(self, system_prompt: str, user_message: str) -> str:
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...


class DeepSeekClient(LLMClient):
    def __init__(self):
        self.api_key = settings.deepseek_api_key
        self.base_url = settings.deepseek_base_url

    async def chat(self, system_prompt: str, user_message: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2048,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": "deepseek-chat", "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]


def get_llm() -> LLMClient:
    return DeepSeekClient()
