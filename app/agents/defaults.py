from app.agents.image_prompt import ImagePromptAgent
from app.agents.narration import NarrationAgent
from app.agents.registry import AgentRegistry
from app.agents.research import ResearchAgent
from app.agents.script import ScriptAgent
from app.agents.seo import SEOAgent
from app.agents.storyboard import StoryboardAgent
from app.agents.video_prompt import VideoPromptAgent


def register_default_agents() -> None:
    """Register DocuForge's built-in agents."""

    if AgentRegistry.all():
        return

    AgentRegistry.register(
        key="research",
        name="Research",
        icon="🔍",
        output_file="research.md",
        factory=ResearchAgent,
    )

    AgentRegistry.register(
        key="script",
        name="Script",
        icon="🎬",
        output_file="script.md",
        factory=ScriptAgent,
    )

    AgentRegistry.register(
        key="storyboard",
        name="Storyboard",
        icon="🎞",
        output_file="storyboard.json",
        factory=StoryboardAgent,
    )

    AgentRegistry.register(
        key="images",
        name="Image Prompts",
        icon="🖼",
        output_file="image_prompts.json",
        factory=ImagePromptAgent,
    )

    AgentRegistry.register(
        key="videos",
        name="Video Prompts",
        icon="🎥",
        output_file="video_prompts.json",
        factory=VideoPromptAgent,
    )

    AgentRegistry.register(
        key="narration",
        name="Narration",
        icon="🎙",
        output_file="narration.txt",
        factory=NarrationAgent,
    )

    AgentRegistry.register(
        key="seo",
        name="SEO Metadata",
        icon="📈",
        output_file="seo.json",
        factory=SEOAgent,
    )
