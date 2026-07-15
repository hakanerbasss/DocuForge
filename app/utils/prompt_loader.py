from pathlib import Path
from jinja2 import Environment, FileSystemLoader


PROMPTS_DIR = Path("app/prompts")

env = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def load_prompt(name: str, **kwargs) -> str:
    template = env.get_template(f"{name}.txt")
    return template.render(**kwargs)
