from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class ModelConfig:
    model_name: str
    api_key: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float = 0.9


@dataclass
class Prompts:
    system: str


class LLMError(Exception):
    pass

class BaseLLM(ABC):

    def __init__(self, cfg: ModelConfig, prompts: Prompts):
        self.cfg = cfg
        self.prompts = prompts

    @abstractmethod
    def send_message(self, user_message: str) -> str:
        """Return model-generated text"""
        pass
