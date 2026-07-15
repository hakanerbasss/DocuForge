from app.agents.base import BaseAgent
from app.utils.prompt_loader import load_prompt


class ScriptAgent(BaseAgent):
    """Generate a script from research."""

    def run(
        self,
        research: str,
        language: str = "en",
        content_type: str = "documentary",
        target_duration_seconds: int = 600,
    ) -> str:
        prompt = load_prompt(
            "script",
            research=research,
            language=language,
            content_type=content_type,
            target_duration_seconds=target_duration_seconds,
            target_duration_minutes=round(target_duration_seconds / 60, 1),
        )
        response = self.generate_with_retry(prompt)
        return self.validate_text(response)
