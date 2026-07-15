from app.agents.base import BaseAgent
from app.utils.prompt_loader import load_prompt


class ScriptAgent(BaseAgent):
    """Generate a documentary script from research."""

    def run(
        self,
        research: str,
        language: str = "en",
    ) -> str:
        prompt = load_prompt(
            "script",
            research=research,
            language=language,
        )

        response = self.generate_with_retry(prompt)

        return self.validate_text(response)
