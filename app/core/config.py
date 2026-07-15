from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass
class Settings:
    project_name: str = "DocuForge"
    version: str = "0.1.0"
    environment: str = os.getenv("ENVIRONMENT", "development")

    ai_provider: str = os.getenv("AI_PROVIDER", "deepseek")
    model: str = os.getenv("MODEL", "deepseek-chat")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")

settings = Settings()
