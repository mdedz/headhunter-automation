from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Optional, Union, get_type_hints

import tomllib


@dataclass
class Proxy:
    proxy_url: str = ""


@dataclass
class Candidate:
    info: str = ""


@dataclass
class DefaultChatReply:
    message: str = ""


@dataclass
class DefaultCoverLetter:
    messages: str = ""


@dataclass
class DefaultMessages:
    chat_reply: DefaultChatReply = field(default_factory=DefaultChatReply)
    cover_letter: DefaultCoverLetter = field(default_factory=DefaultCoverLetter)


@dataclass
class LLMOptions:
    provider: str = ""
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float = 0.9
    api_key: Optional[str] = None


@dataclass
class LLMPrompts:
    system: str = ""


@dataclass
class CoverLettersMessages:
    footer_msg: str = ""


@dataclass
class CoverLetters:
    options: LLMOptions = field(default_factory=LLMOptions)
    prompts: LLMPrompts = field(default_factory=LLMPrompts)
    messages: CoverLettersMessages = field(default_factory=CoverLettersMessages)


@dataclass
class VerifyRelevance:
    options: LLMOptions = field(default_factory=LLMOptions)
    prompts: LLMPrompts = field(default_factory=LLMPrompts)


@dataclass
class ChatReply:
    options: LLMOptions = field(default_factory=LLMOptions)
    prompts: LLMPrompts = field(default_factory=LLMPrompts)

@dataclass
class ResumeBuilder:
    options: LLMOptions = field(default_factory=LLMOptions)
    prompts: LLMPrompts = field(default_factory=LLMPrompts)

@dataclass
class LLMConfig:
    cover_letters: CoverLetters = field(default_factory=CoverLetters)
    verify_relevance: VerifyRelevance = field(default_factory=VerifyRelevance)
    chat_reply: ChatReply = field(default_factory=ChatReply)
    resume_builder: ResumeBuilder = field(default_factory=ResumeBuilder)


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    candidate: Candidate = field(default_factory=Candidate)
    default_messages: DefaultMessages = field(default_factory=DefaultMessages)
    proxy: Proxy = field(default_factory=Proxy)

    @classmethod
    def load(cls, config_path: str | Path = "config/config.toml") -> Config:
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"{config_path} does not exist")

        with config_path.open("rb") as f:
            data = tomllib.load(f)

        def to_dc(cls_type, d: dict[str, Any]):
            if not is_dataclass(cls_type):
                return d

            kwargs = {}
            hints = get_type_hints(cls_type)  # resolves forward refs
            for f in fields(cls_type):
                name = f.name
                if name not in d:
                    continue
                value = d[name]
                f_type = hints.get(name, f.type)

                # unwrap Optional[T]
                origin = getattr(f_type, "__origin__", None)
                args = getattr(f_type, "__args__", ())
                if origin is Union and type(None) in args:
                    non_none = [a for a in args if a is not type(None)]
                    if non_none:
                        f_type = non_none[0]

                if is_dataclass(f_type) and isinstance(value, dict):
                    kwargs[name] = to_dc(f_type, value)
                else:
                    kwargs[name] = value

            return cls_type(**kwargs)  # type: ignore

        return to_dc(cls, data)  # type: ignore
