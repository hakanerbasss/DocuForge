from openai import OpenAI

from app.core.config import settings
from app.providers.base import TextProvider


class DeepSeekProvider(TextProvider):
    """DeepSeek text generation provider."""

    provider_key = "deepseek"
    provider_name = "DeepSeek"

    def __init__(self) -> None:
        super().__init__()

        if not settings.deepseek_api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY is not configured."
            )

        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=settings.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.7,
            max_tokens=8192,
        )

        content = response.choices[0].message.content

        if not isinstance(content, str) or not content.strip():
            raise ValueError(
                "DeepSeek returned an empty response."
            )

        return content.strip()
