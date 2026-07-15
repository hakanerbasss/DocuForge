from app.ai.factory import get_ai
from app.utils.prompt_loader import load_prompt


class ResearchAgent:
    def __init__(self):
        self.ai = get_ai()

    def run(self, topic: str) -> str:
        prompt = load_prompt(
            "research",
            topic=topic,
        )

        return self.ai.generate(prompt)
