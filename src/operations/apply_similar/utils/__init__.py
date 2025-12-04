import logging
from ai import LLMFactory
from ai.base import ModelConfig, Prompts
from config import Candidate, LLMOptions, LLMPrompts

logger = logging.getLogger(__package__)

def get_chat(cfg_prompts: LLMPrompts, options: LLMOptions, candidate: Candidate):
    cfg = ModelConfig(
        options.model_name,
        options.api_key,
        options.temperature,
        options.max_tokens,
        options.top_p,
        )
    
    system_prompt = cfg_prompts.system + "\n" + candidate.info 
    
    prompts = Prompts(
        system_prompt
    )
    
    return LLMFactory.create(options.provider, cfg, prompts)
