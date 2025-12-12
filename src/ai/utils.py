from ai import LLMFactory
from ai.base import ModelConfig, Prompts
from config import Candidate, LLMOptions, LLMPrompts


def get_prompts(cfg_prompts: LLMPrompts, candidate_info: Candidate | None = None) -> Prompts:
    system_prompt = cfg_prompts.system
    if candidate_info:
        system_prompt += "\n" + candidate_info.info

    return Prompts(system_prompt)


def get_chat(prompts: Prompts, options: LLMOptions):
    cfg = ModelConfig(
        options.model_name,
        options.api_key,
        options.temperature,
        options.max_tokens,
        options.top_p,
    )

    return LLMFactory.create(options.provider, cfg, prompts)
