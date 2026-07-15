from app.agents.base import BaseAgent
from app.utils.prompt_loader import load_prompt


class ResearchAgent(BaseAgent):
    """Generate documentary research from a topic."""

    def run(
        self,
        topic: str,
        language: str = "en",
    ) -> str:
        prompt = load_prompt(
            "research",
            topic=topic,
            language=language,
        )

        response = self.generate_with_retry(prompt)

        return self.validate_text(response)
