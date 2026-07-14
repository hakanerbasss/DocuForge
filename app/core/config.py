from dataclasses import dataclass


@dataclass
class Settings:
    project_name: str = "DocuForge"
    version: str = "0.1.0"
    environment: str = "development"


settings = Settings()
