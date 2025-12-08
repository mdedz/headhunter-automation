import logging
import time

from src.ai.base import BaseLLM, LLMError, ModelConfig, Prompts

logger = logging.getLogger(__package__)


class GroqLLM(BaseLLM):
    def __init__(self, cfg: ModelConfig, prompts: Prompts):
        super().__init__(cfg, prompts)
        from groq import Groq
        if not cfg.api_key:
            raise LLMError(
                "No api key is defined in config.toml"
            )

        self.client = Groq(api_key=cfg.api_key)

    def send_message(self, user_message: str, verify_tag_end: bool = False) -> str:
        try:
            messages = [
                {"role": "system", "content": self.prompts.system},
                {"role": "user", "content": user_message}
            ]

            response = ""
            finished = False
            retry_count = 0

            while not finished and retry_count < 3:
                completion = self.client.chat.completions.create(
                    model=self.cfg.model_name,
                    messages=messages, # type: ignore
                    temperature=self.cfg.temperature,
                    max_tokens=self.cfg.max_tokens,
                    top_p=self.cfg.top_p,
                )

                content = completion.choices[0].message.content
                if not content: continue

                part = content.strip()
                response += " " + part.strip()

                if verify_tag_end:
                    #if msg is not complete then proceed generating
                    if "<END>" in part:
                        finished = True
                        response = response.replace("<END>", "").strip()
                    else:
                        messages.append({"role": "user", "content": "Продолжи письмо, пожалуйста, с того места, где остановился."})
                        retry_count += 1
                        time.sleep(0.5)
                else:
                    finished = True

            if not finished:
                logger.warning("Письмо могло быть обрезано, но достигнут лимит повторов.")

            logger.info("Generated msg: %s", response)
            return response

        except Exception as ex:
            raise LLMError(f"{ex}") from ex
