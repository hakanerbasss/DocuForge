import json
from typing import Any

from app.agents.base import BaseAgent


class NarrationAgent(BaseAgent):
    """Extract and format narration text from storyboard JSON."""

    def run(self, storyboard: str) -> str:
        data = self._parse_storyboard(storyboard)
        scenes = data["scenes"]

        narration_parts: list[str] = []

        for scene in scenes:
            scene_number = scene["scene"]
            narration = scene["narration"].strip()

            narration_parts.append(
                f"[Scene {scene_number}]\n{narration}"
            )

        result = "\n\n".join(narration_parts)

        return self.validate_text(result)

    def _parse_storyboard(self, storyboard: str) -> dict[str, Any]:
        try:
            data = json.loads(storyboard)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Storyboard is not valid JSON: {error}"
            ) from error

        if not isinstance(data, dict):
            raise ValueError(
                "Storyboard root must be a JSON object."
            )

        scenes = data.get("scenes")

        if not isinstance(scenes, list) or not scenes:
            raise ValueError(
                "Storyboard must contain a non-empty 'scenes' list."
            )

        for index, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                raise ValueError(
                    f"Scene {index} must be a JSON object."
                )

            if "scene" not in scene:
                raise ValueError(
                    f"Scene {index} is missing the 'scene' field."
                )

            narration = scene.get("narration")

            if not isinstance(narration, str) or not narration.strip():
                raise ValueError(
                    f"Scene {index} has invalid narration."
                )

        return data
