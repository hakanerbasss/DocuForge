from openai import OpenAI

from app.core.config import settings


class DeepSeekProvider:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com"
        )

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=settings.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=4000,
        )

        return response.choices[0].message.content
