from pathlib import Path

from app.pipeline.pipeline import Pipeline


def generate(topic: str) -> Path:

    pipeline = Pipeline()

    return pipeline.generate(topic)
