from abc import ABC, abstractmethod


class AIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate_content(self, prompt: str) -> str:
        raise NotImplementedError

    @property
    def is_configured(self) -> bool:
        return True
