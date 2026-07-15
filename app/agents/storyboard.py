import json
from typing import Any

from app.agents.base import BaseAgent
from app.utils.prompt_loader import load_prompt


class StoryboardAgent(BaseAgent):
    """Generate and validate a documentary storyboard."""

    def run(
        self,
        script: str,
        language: str = "en",
    ) -> str:
        last_error: Exception | None = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            prompt = load_prompt(
                "storyboard",
                script=script,
                language=language,
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
                storyboard = self._parse_and_validate(response)

                return json.dumps(
                    storyboard,
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
            "Storyboard could not be generated as valid JSON "
            f"after {self.MAX_ATTEMPTS} attempts. "
            f"Last error: {last_error}"
        )

    def _parse_and_validate(
        self,
        response: str,
    ) -> dict[str, Any]:
        cleaned_response = self._remove_code_fences(response)
        data = json.loads(cleaned_response)

        if not isinstance(data, dict):
            raise ValueError(
                "Storyboard root must be a JSON object."
            )

        scenes = data.get("scenes")

        if not isinstance(scenes, list):
            raise ValueError(
                "Storyboard must contain a 'scenes' list."
            )

        if not scenes:
            raise ValueError(
                "Storyboard must contain at least one scene."
            )

        for index, scene in enumerate(scenes, start=1):
            self._validate_scene(scene, index)

        return data

    def _validate_scene(
        self,
        scene: Any,
        index: int,
    ) -> None:
        if not isinstance(scene, dict):
            raise ValueError(
                f"Scene {index} must be a JSON object."
            )

        required_fields = {
            "scene",
            "title",
            "duration",
            "narration",
            "visual",
        }

        missing_fields = required_fields - scene.keys()

        if missing_fields:
            missing = ", ".join(sorted(missing_fields))

            raise ValueError(
                f"Scene {index} is missing fields: {missing}"
            )

        if not isinstance(scene["scene"], int):
            raise ValueError(
                f"Scene {index}: 'scene' must be an integer."
            )

        if not isinstance(scene["duration"], int):
            raise ValueError(
                f"Scene {index}: 'duration' must be an integer."
            )

        if not 1 <= scene["duration"] <= 60:
            raise ValueError(
                f"Scene {index}: duration must be "
                "between 1 and 60 seconds."
            )

        for field in ("title", "narration", "visual"):
            value = scene[field]

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Scene {index}: '{field}' must be "
                    "a non-empty string."
                )

    def _remove_code_fences(
        self,
        response: str,
    ) -> str:
        cleaned = response.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned[len("```json"):]

        elif cleaned.startswith("```"):
            cleaned = cleaned[len("```"):]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        return cleaned.strip()
