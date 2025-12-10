from src.ai.base import ModelConfig, Prompts
from src.ai.models.groq import GroqLLM


class LLMFactory:
    providers = {
        "groq": GroqLLM,
    }

    @classmethod
    def create(cls, provider: str, cfg: ModelConfig, prompts: Prompts):
        if provider not in cls.providers:
            raise ValueError(f"Unknown provider: {provider}")
        return cls.providers[provider](cfg, prompts)
