import time
from typing import Any

import requests


class FalQueueClient:
    """Shared submit/poll/result logic for fal.ai's queue REST API.

    Docs: https://docs.fal.ai/model-apis/model-endpoints/queue
    Response field names vary per model family (flux vs. kling vs. ...),
    so callers are responsible for picking the right key out of the
    final result payload.
    """

    BASE_URL = "https://queue.fal.run"
    POLL_INTERVAL_SECONDS = 3
    MAX_WAIT_SECONDS = 600

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("FAL_KEY is not configured.")

        self.headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }

    def run(
        self,
        model_endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Submit a job, poll until complete, and return the result payload."""

        submission = self._submit(model_endpoint, payload)
        status_url = submission["status_url"]
        response_url = submission["response_url"]

        self._poll_until_completed(status_url)

        response = requests.get(
            response_url,
            headers=self.headers,
            timeout=60,
        )
        response.raise_for_status()

        return response.json()

    def _submit(
        self,
        model_endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = requests.post(
            f"{self.BASE_URL}/{model_endpoint}",
            headers=self.headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        if "status_url" not in data or "response_url" not in data:
            raise RuntimeError(
                f"Unexpected fal.ai submit response: {data}"
            )

        return data

    def _poll_until_completed(self, status_url: str) -> None:
        elapsed = 0

        while elapsed < self.MAX_WAIT_SECONDS:
            response = requests.get(
                status_url,
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()
            status = response.json().get("status")

            if status == "COMPLETED":
                return

            if status in ("ERROR", "FAILED"):
                raise RuntimeError(
                    f"fal.ai job failed: {response.json()}"
                )

            time.sleep(self.POLL_INTERVAL_SECONDS)
            elapsed += self.POLL_INTERVAL_SECONDS

        raise TimeoutError(
            f"fal.ai job did not complete within {self.MAX_WAIT_SECONDS}s."
        )
