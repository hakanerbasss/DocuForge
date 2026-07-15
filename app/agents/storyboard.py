from app.ai.factory import get_ai
from app.utils.prompt_loader import load_prompt


class StoryboardAgent:
    def __init__(self):
        self.ai = get_ai()

    def run(self, script: str) -> str:
        prompt = load_prompt(
            "storyboard",
            script=script,
        )

        return self.ai.generate(prompt)
