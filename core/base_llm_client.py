from typing import Generator, Optional


class BaseLLMClient:
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        raise NotImplementedError()

    def generate_sync(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        raise NotImplementedError()
