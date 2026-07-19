import json
from typing import Any

from app.agents.base import BaseAgent
from app.utils.prompt_loader import load_prompt


class ImagePromptAgent(BaseAgent):
    """Generate and validate image prompts from a storyboard."""

    def run(self, storyboard: str) -> str:
        last_error: Exception | None = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            prompt = load_prompt(
                "image",
                storyboard=storyboard,
            )

            if attempt > 1:
                prompt += """

Your previous response was invalid.

Return ONLY valid JSON.
Do not use Markdown code fences.
Do not include explanations before or after the JSON.
"""

            try:
                response = self.generate_with_retry(prompt)
                data = self._parse_and_validate(response)

                return json.dumps(
                    data,
                    ensure_ascii=False,
                    indent=2,
                )

            except (
                json.JSONDecodeError,
                ValueError,
                TypeError,
            ) as error:
                last_error = error

        raise ValueError(
            "Image prompts could not be generated as valid JSON "
            f"after {self.MAX_ATTEMPTS} attempts. "
            f"Last error: {last_error}"
        )

    def _parse_and_validate(self, response: str) -> dict[str, Any]:
        cleaned_response = self._remove_code_fences(response)
        data = json.loads(cleaned_response)

        if not isinstance(data, dict):
            raise ValueError("Image prompt output must be a JSON object.")

        images = data.get("images")

        if not isinstance(images, list):
            raise ValueError(
                "Image prompt output must contain an 'images' list."
            )

        if not images:
            raise ValueError(
                "Image prompt output must contain at least one item."
            )

        for index, image in enumerate(images, start=1):
            self._validate_image(image, index)

        return data

    def _validate_image(
        self,
        image: Any,
        index: int,
    ) -> None:
        if not isinstance(image, dict):
            raise ValueError(
                f"Image item {index} must be a JSON object."
            )

        required_fields = {"scene", "prompt"}
        missing_fields = required_fields - image.keys()

        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(
                f"Image item {index} is missing fields: {missing}"
            )

        if not isinstance(image["scene"], int):
            raise ValueError(
                f"Image item {index}: 'scene' must be an integer."
            )

        prompt = image["prompt"]

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(
                f"Image item {index}: 'prompt' "
                "must be a non-empty string."
            )

    def _remove_code_fences(self, response: str) -> str:
        cleaned = response.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned[len("```json"):]

        elif cleaned.startswith("```"):
            cleaned = cleaned[len("```"):]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        return cleaned.strip()
