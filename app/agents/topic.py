import json
from typing import Any

from app.agents.base import BaseAgent
from app.utils.prompt_loader import load_prompt


class TopicSuggestionAgent(BaseAgent):
    """Suggest high-CTR video topic ideas for the /new wizard."""

    def run(
        self,
        language: str = "tr",
        content_type: str = "documentary",
    ) -> str:
        last_error: Exception | None = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            prompt = load_prompt(
                "topic_suggestions",
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
                suggestions = self._parse_and_validate(response)

                return json.dumps(
                    suggestions,
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
            "Topic suggestions could not be generated as valid JSON "
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
                "Topic suggestions root must be a JSON object."
            )

        suggestions = data.get("suggestions")

        if not isinstance(suggestions, list) or not suggestions:
            raise ValueError(
                "Topic suggestions must contain a non-empty 'suggestions' list."
            )

        cleaned: list[dict[str, str]] = []

        for index, item in enumerate(suggestions, start=1):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Suggestion {index} must be a JSON object."
                )

            title = item.get("title")

            if not isinstance(title, str) or not title.strip():
                raise ValueError(
                    f"Suggestion {index} is missing a non-empty 'title'."
                )

            cleaned.append({
                "title": title.strip(),
                "hook": self._optional_str(item.get("hook")),
                "visual_left": self._optional_str(item.get("visual_left")),
                "visual_right": self._optional_str(item.get("visual_right")),
            })

        return {"suggestions": cleaned}

    def _optional_str(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""

        return value.strip()

    def _remove_code_fences(self, text: str) -> str:
        cleaned = text.strip()

        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            cleaned = "\n".join(lines).strip()

        return cleaned
