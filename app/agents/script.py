from app.ai.factory import get_ai
from app.utils.prompt_loader import load_prompt


class ScriptAgent:
    def __init__(self):
        self.ai = get_ai()

    def run(self, research: str) -> str:
        prompt = load_prompt(
            "script",
            research=research,
        )

        return self.ai.generate(prompt)
