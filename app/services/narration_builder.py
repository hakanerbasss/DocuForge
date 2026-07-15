import json
from pathlib import Path
from typing import Any


class NarrationBuilder:
    """Create scene-based narration text files from storyboard JSON."""

    def build(self, project_path: str) -> Path:
        project_dir = Path(project_path)
        storyboard_path = project_dir / "storyboard.json"
        audio_dir = project_dir / "audio"

        if not project_dir.exists():
            raise FileNotFoundError(
                f"Project directory not found: {project_dir}"
            )

        if not storyboard_path.exists():
            raise FileNotFoundError(
                f"storyboard.json not found: {storyboard_path}"
            )

        storyboard = self._load_storyboard(storyboard_path)

        audio_dir.mkdir(parents=True, exist_ok=True)

        manifest_scenes: list[dict[str, Any]] = []

        for index, scene in enumerate(
            storyboard["scenes"],
            start=1,
        ):
            scene_number = self._get_scene_number(
                scene=scene,
                fallback=index,
            )

            narration = self._get_narration(
                scene=scene,
                scene_number=scene_number,
            )

            duration = self._get_duration(scene)

            text_path = audio_dir / f"scene_{scene_number:03d}.txt"

            text_path.write_text(
                narration,
                encoding="utf-8",
            )

            manifest_scenes.append(
                {
                    "scene": scene_number,
                    "text_file": str(text_path),
                    "audio_file": str(
                        audio_dir / f"scene_{scene_number:03d}.wav"
                    ),
                    "storyboard_duration": duration,
                    "audio_duration": None,
                    "status": "text_ready",
                }
            )

        manifest_path = audio_dir / "manifest.json"

        manifest_path.write_text(
            json.dumps(
                {
                    "project": str(project_dir),
                    "scene_count": len(manifest_scenes),
                    "scenes": manifest_scenes,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return manifest_path

    def _load_storyboard(
        self,
        storyboard_path: Path,
    ) -> dict[str, Any]:
        try:
            data = json.loads(
                storyboard_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                f"storyboard.json is invalid: {error}"
            ) from error

        if not isinstance(data, dict):
            raise ValueError(
                "Storyboard root must be a JSON object."
            )

        scenes = data.get("scenes")

        if not isinstance(scenes, list) or not scenes:
            raise ValueError(
                "Storyboard must contain a non-empty scenes list."
            )

        return data

    def _get_scene_number(
        self,
        scene: Any,
        fallback: int,
    ) -> int:
        if not isinstance(scene, dict):
            raise ValueError(
                f"Scene {fallback} must be a JSON object."
            )

        value = scene.get("scene", fallback)

        try:
            scene_number = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid scene number at position {fallback}: {value}"
            ) from error

        if scene_number < 1:
            raise ValueError(
                f"Scene number must be greater than zero: {scene_number}"
            )

        return scene_number

    def _get_narration(
        self,
        scene: dict[str, Any],
        scene_number: int,
    ) -> str:
        narration = scene.get("narration")

        if not isinstance(narration, str) or not narration.strip():
            raise ValueError(
                f"Scene {scene_number} has no valid narration."
            )

        return narration.strip()

    def _get_duration(
        self,
        scene: dict[str, Any],
    ) -> float:
        value = scene.get("duration", 8)

        try:
            duration = float(value)
        except (TypeError, ValueError):
            return 8.0

        if duration <= 0:
            return 8.0

        return duration
