from app.core.config import settings
from app.ai.deepseek import DeepSeekProvider


def get_ai():
    provider = settings.ai_provider.lower()

    if provider == "deepseek":
        return DeepSeekProvider()

    raise ValueError(f"Unsupported AI provider: {provider}")
