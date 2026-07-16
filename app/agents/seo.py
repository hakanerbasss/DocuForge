import json
from typing import Any

from app.agents.base import BaseAgent
from app.utils.prompt_loader import load_prompt


class SEOAgent(BaseAgent):
    """Generate YouTube title suggestions, description, and tags."""

    def run(
        self,
        script: str,
        language: str = "en",
        content_type: str = "documentary",
        target_duration_seconds: int = 600,
    ) -> str:
        last_error: Exception | None = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            prompt = load_prompt(
                "seo",
                script=script,
                language=language,
                content_type=content_type,
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
                seo_data = self._parse_and_validate(response)

                return json.dumps(
                    seo_data,
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
            "SEO metadata could not be generated as valid JSON "
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
                "SEO metadata root must be a JSON object."
            )

        titles = data.get("titles")

        if not isinstance(titles, list) or not titles:
            raise ValueError(
                "SEO metadata must contain a non-empty 'titles' list."
            )

        for index, title in enumerate(titles, start=1):
            if not isinstance(title, str) or not title.strip():
                raise ValueError(
                    f"Title {index} must be a non-empty string."
                )

        description = data.get("description")

        if not isinstance(description, str) or not description.strip():
            raise ValueError(
                "SEO metadata must contain a non-empty 'description' string."
            )

        tags = data.get("tags")

        if not isinstance(tags, list) or not tags:
            raise ValueError(
                "SEO metadata must contain a non-empty 'tags' list."
            )

        for index, tag in enumerate(tags, start=1):
            if not isinstance(tag, str) or not tag.strip():
                raise ValueError(
                    f"Tag {index} must be a non-empty string."
                )

        return {
            "titles": [title.strip() for title in titles],
            "description": description.strip(),
            "tags": [tag.strip() for tag in tags],
            "thumbnail_hook": self._optional_str(data, "thumbnail_hook"),
            "main_subject": self._optional_str(data, "main_subject"),
            "emotional_trigger": self._optional_str(data, "emotional_trigger"),
            "visual_contrast": self._optional_str(data, "visual_contrast"),
            "text_overlay": self._optional_str(data, "text_overlay"),
            "avoid_elements": self._optional_str(data, "avoid_elements"),
        }

    def _optional_str(self, data: dict[str, Any], key: str) -> str:
        """Thumbnail creative-brief fields are best-effort: a missing or
        malformed value falls back to an empty string instead of failing
        the whole SEO generation, since titles/description/tags remain
        the only hard requirement.
        """

        value = data.get(key, "")
        return value.strip() if isinstance(value, str) else ""

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
