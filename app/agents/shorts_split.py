import json
from typing import Any

from app.agents.base import BaseAgent
from app.utils.prompt_loader import load_prompt


class ShortsSplitAgent(BaseAgent):
    """Repurpose a finished long-form script into independent Shorts."""

    def run(
        self,
        script: str,
        language: str = "tr",
        count: int = 10,
    ) -> str:
        last_error: Exception | None = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            prompt = load_prompt(
                "shorts_split",
                script=script,
                language=language,
                count=count,
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
                data = self._parse_and_validate(response, count)

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
            "Shorts could not be generated as valid JSON "
            f"after {self.MAX_ATTEMPTS} attempts. "
            f"Last error: {last_error}"
        )

    def _parse_and_validate(
        self,
        response: str,
        count: int,
    ) -> dict[str, Any]:
        cleaned_response = self._remove_code_fences(response)
        data = json.loads(cleaned_response)

        if not isinstance(data, dict):
            raise ValueError("Shorts output must be a JSON object.")

        shorts = data.get("shorts")

        if not isinstance(shorts, list) or not shorts:
            raise ValueError(
                "Shorts output must contain a non-empty 'shorts' list."
            )

        cleaned: list[dict[str, str]] = []

        for index, item in enumerate(shorts, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"Short {index} must be a JSON object.")

            title = item.get("title")
            hook = item.get("hook")
            script = item.get("script")

            for field_name, value in (
                ("title", title),
                ("hook", hook),
                ("script", script),
            ):
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(
                        f"Short {index} is missing a non-empty '{field_name}'."
                    )

            cleaned.append({
                "title": title.strip(),
                "hook": hook.strip(),
                "script": script.strip(),
            })

        return {"shorts": cleaned}

    def _remove_code_fences(self, response: str) -> str:
        cleaned = response.strip()

        if cleaned.startswith("```json"):
            cleaned = cleaned[len("```json"):]

        elif cleaned.startswith("```"):
            cleaned = cleaned[len("```"):]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        return cleaned.strip()
