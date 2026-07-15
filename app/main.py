import time
import typer
from app.services.voice_service import VoiceService
from app.services.narration_builder import NarrationBuilder
from app.services.media_builder import MediaBuilder
from app.agents.narration import NarrationAgent
from app.agents.video_prompt import VideoPromptAgent
from app.agents.image_prompt import ImagePromptAgent
from app.pipeline.build_pipeline import BuildPipeline
from pathlib import Path
from app.agents.storyboard import StoryboardAgent
from rich.console import Console
from app.agents.script import ScriptAgent
from app.core.config import settings
from app.agents.research import ResearchAgent
from app.services.project_service import load_project
from app.services.render_service import RenderService

app = typer.Typer(
    help="AI-powered documentary production platform."
)

console = Console()


@app.command()
def version():
    """Show version information."""
    console.print(f"[bold cyan]{settings.project_name}[/bold cyan]")
    console.print(f"Version: {settings.version}")
    console.print("[green]Status: Ready[/green]")


@app.command()
def research(project: str):
    """Generate research for an existing project."""

    project_data = load_project(project)

    console.print("\n[bold cyan]🔍 Research Agent[/bold cyan]\n")
    console.print(f"[bold]📂 Project :[/bold] {project_data['title']}")
    console.print("[bold]🤖 Model   :[/bold] DeepSeek Chat")
    console.print("[bold]📝 Step    :[/bold] Research\n")

    start = time.perf_counter()

    console.print("[yellow]⏳ Generating research...[/yellow]")

    agent = ResearchAgent()
    result = agent.run(project_data["title"])

    with open(f"{project}/research.md", "w", encoding="utf-8") as f:
        f.write(result)

    elapsed = time.perf_counter() - start

    console.print("\n[bold green]✅ research.md created[/bold green]")
    console.print(f"[cyan]⏱ Completed in {elapsed:.2f} seconds[/cyan]")

@app.command()
def script(project: str):
    """Generate documentary script."""

    import time
    from pathlib import Path

    console.print("\n[bold cyan]🎬 Script Agent[/bold cyan]\n")

    project_data = load_project(project)

    console.print(f"[bold]📂 Project :[/bold] {project_data['title']}")
    console.print("[bold]🤖 Model   :[/bold] DeepSeek Chat")
    console.print("[bold]📝 Step    :[/bold] Script\n")

    research_file = Path(project) / "research.md"

    if not research_file.exists():
        console.print("[red]research.md not found[/red]")
        raise typer.Exit()

    research = research_file.read_text(encoding="utf-8")

    start = time.perf_counter()

    console.print("[yellow]⏳ Generating documentary script...[/yellow]")

    agent = ScriptAgent()

    script = agent.run(research)

    (Path(project) / "script.md").write_text(
        script,
        encoding="utf-8"
    )

    elapsed = time.perf_counter() - start

    console.print("\n[green]✅ script.md created[/green]")
    console.print(f"[cyan]⏱ Completed in {elapsed:.2f} seconds[/cyan]")

@app.command()
def storyboard(project: str):
    """Generate storyboard from script."""

    import time

    console.print("\n[bold cyan]🎞 Storyboard Agent[/bold cyan]\n")

    project_data = load_project(project)

    console.print(f"[bold]📂 Project :[/bold] {project_data['title']}")
    console.print("[bold]🤖 Model   :[/bold] DeepSeek Chat")
    console.print("[bold]📝 Step    :[/bold] Storyboard\n")

    script_file = Path(project) / "script.md"

    if not script_file.exists():
        console.print("[red]❌ script.md not found[/red]")
        raise typer.Exit()

    script = script_file.read_text(encoding="utf-8")

    start = time.perf_counter()

    console.print("[yellow]⏳ Generating storyboard...[/yellow]")

    agent = StoryboardAgent()

    storyboard = agent.run(script)

    (Path(project) / "storyboard.json").write_text(
        storyboard,
        encoding="utf-8"
    )

    elapsed = time.perf_counter() - start

    console.print("\n[bold green]✅ storyboard.json created[/bold green]")
    console.print(f"[cyan]⏱ Completed in {elapsed:.2f} seconds[/cyan]")

@app.command()
def build(topic: str):
    """Generate a complete documentary project."""

    import time

    start = time.perf_counter()

    console.print("\n[bold green]🚀 DocuForge Build Pipeline[/bold green]\n")

    console.print(f"[bold]📖 Topic:[/bold] {topic}\n")

    pipeline = BuildPipeline()

    project_dir = pipeline.run(topic)

    elapsed = time.perf_counter() - start

    console.print("\n[bold green]🎉 Build completed successfully![/bold green]")
    console.print(f"[bold]📁 Project:[/bold] {project_dir}")
    console.print(f"[cyan]⏱ Total time: {elapsed:.2f} seconds[/cyan]")

@app.command()
def resume(project: str):
    """Resume an interrupted documentary build."""

    import time

    start = time.perf_counter()

    console.print("\n[bold yellow]▶ DocuForge Resume Pipeline[/bold yellow]\n")
    console.print(f"[bold]📁 Project:[/bold] {project}\n")

    pipeline = BuildPipeline()
    project_dir = pipeline.resume(project)

    elapsed = time.perf_counter() - start

    console.print(
        "\n[bold green]🎉 Pipeline resumed and completed successfully!"
        "[/bold green]"
    )
    console.print(f"[bold]📁 Project:[/bold] {project_dir}")
    console.print(f"[cyan]⏱ Total time: {elapsed:.2f} seconds[/cyan]")

@app.command("images")
def images_command(project: str):
    """Generate image prompts from storyboard."""

    import time
    from pathlib import Path

    console.print("\n[bold cyan]🖼 Image Prompt Agent[/bold cyan]\n")

    project_data = load_project(project)

    console.print(f"[bold]📂 Project :[/bold] {project_data['title']}")
    console.print("[bold]🤖 Model   :[/bold] DeepSeek Chat")
    console.print("[bold]📝 Step    :[/bold] Image Prompts\n")

    storyboard_file = Path(project) / "storyboard.json"

    if not storyboard_file.exists():
        console.print("[bold red]❌ storyboard.json not found[/bold red]")
        raise typer.Exit(code=1)

    storyboard_content = storyboard_file.read_text(
        encoding="utf-8"
    ).strip()

    if not storyboard_content:
        console.print("[bold red]❌ storyboard.json is empty[/bold red]")
        raise typer.Exit(code=1)

    start = time.perf_counter()

    console.print(
        "[yellow]⏳ Generating image prompts...[/yellow]"
    )

    try:
        result = ImagePromptAgent().run(storyboard_content)
    except Exception as error:
        console.print(
            f"\n[bold red]❌ Image Prompt Agent failed[/bold red]"
        )
        console.print(f"[red]Error: {error}[/red]")
        raise typer.Exit(code=1)

    output_file = Path(project) / "image_prompts.json"
    output_file.write_text(
        result,
        encoding="utf-8",
    )

    elapsed = time.perf_counter() - start

    console.print(
        "\n[bold green]✅ image_prompts.json created[/bold green]"
    )
    console.print(
        f"[cyan]⏱ Completed in {elapsed:.2f} seconds[/cyan]"
    )

@app.command("videos")
def videos_command(project: str):
    """Generate video prompts from storyboard."""

    import time
    from pathlib import Path

    console.print("\n[bold cyan]🎥 Video Prompt Agent[/bold cyan]\n")

    project_data = load_project(project)

    console.print(f"[bold]📂 Project :[/bold] {project_data['title']}")
    console.print("[bold]🤖 Model   :[/bold] DeepSeek Chat")
    console.print("[bold]📝 Step    :[/bold] Video Prompts\n")

    storyboard_file = Path(project) / "storyboard.json"

    if not storyboard_file.exists():
        console.print("[bold red]❌ storyboard.json not found[/bold red]")
        raise typer.Exit(code=1)

    storyboard_content = storyboard_file.read_text(
        encoding="utf-8"
    ).strip()

    if not storyboard_content:
        console.print("[bold red]❌ storyboard.json is empty[/bold red]")
        raise typer.Exit(code=1)

    start = time.perf_counter()

    console.print(
        "[yellow]⏳ Generating video prompts...[/yellow]"
    )

    try:
        result = VideoPromptAgent().run(storyboard_content)
    except Exception as error:
        console.print(
            "\n[bold red]❌ Video Prompt Agent failed[/bold red]"
        )
        console.print(f"[red]Error: {error}[/red]")
        raise typer.Exit(code=1)

    output_file = Path(project) / "video_prompts.json"
    output_file.write_text(
        result,
        encoding="utf-8",
    )

    elapsed = time.perf_counter() - start

    console.print(
        "\n[bold green]✅ video_prompts.json created[/bold green]"
    )
    console.print(
        f"[cyan]⏱ Completed in {elapsed:.2f} seconds[/cyan]"
    )

@app.command("narration")
def narration_command(project: str):
    """Generate narration text from storyboard."""

    import time
    from pathlib import Path

    console.print("\n[bold cyan]🎙 Narration Agent[/bold cyan]\n")

    project_data = load_project(project)

    console.print(f"[bold]📂 Project :[/bold] {project_data['title']}")
    console.print("[bold]📝 Step    :[/bold] Narration\n")

    storyboard_file = Path(project) / "storyboard.json"

    if not storyboard_file.exists():
        console.print("[bold red]❌ storyboard.json not found[/bold red]")
        raise typer.Exit(code=1)

    storyboard_content = storyboard_file.read_text(
        encoding="utf-8"
    ).strip()

    if not storyboard_content:
        console.print("[bold red]❌ storyboard.json is empty[/bold red]")
        raise typer.Exit(code=1)

    start = time.perf_counter()

    console.print("[yellow]⏳ Preparing narration text...[/yellow]")

    try:
        result = NarrationAgent().run(storyboard_content)
    except Exception as error:
        console.print("\n[bold red]❌ Narration Agent failed[/bold red]")
        console.print(f"[red]Error: {error}[/red]")
        raise typer.Exit(code=1)

    output_file = Path(project) / "narration.txt"
    output_file.write_text(
        result,
        encoding="utf-8",
    )

    elapsed = time.perf_counter() - start

    console.print(
        "\n[bold green]✅ narration.txt created[/bold green]"
    )
    console.print(
        f"[cyan]⏱ Completed in {elapsed:.2f} seconds[/cyan]"
    )

@app.command("render")
def render_command(project: str):
    """Render project media into a final MP4 video."""

    import time

    console.print("\n[bold cyan]🎬 FFmpeg Render Engine[/bold cyan]\n")
    console.print(f"[bold]📁 Project:[/bold] {project}\n")
    console.print("[yellow]⏳ Rendering video...[/yellow]")

    start = time.perf_counter()

    try:
        output_path = RenderService().render(project)
    except Exception as error:
        console.print("\n[bold red]❌ Render failed[/bold red]")
        console.print(f"[red]Error: {error}[/red]")
        raise typer.Exit(code=1)

    elapsed = time.perf_counter() - start

    console.print("\n[bold green]✅ final_video.mp4 created[/bold green]")
    console.print(f"[bold]📄 Output:[/bold] {output_path}")
    console.print(f"[cyan]⏱ Completed in {elapsed:.2f} seconds[/cyan]")

@app.command("media")
def media_command(project: str):
    """Download media for every storyboard scene."""

    import time

    console.print("\n[bold cyan]📦 Media Builder[/bold cyan]\n")
    console.print(f"[bold]📁 Project:[/bold] {project}\n")
    console.print("[yellow]⏳ Downloading scene media...[/yellow]\n")

    start = time.perf_counter()

    try:
        manifest_path = MediaBuilder().build(project)
    except Exception as error:
        console.print("\n[bold red]❌ Media Builder failed[/bold red]")
        console.print(f"[red]Error: {error}[/red]")
        raise typer.Exit(code=1)

    elapsed = time.perf_counter() - start

    console.print("\n[bold green]✅ Scene media prepared[/bold green]")
    console.print(f"[bold]📄 Manifest:[/bold] {manifest_path}")
    console.print(f"[cyan]⏱ Completed in {elapsed:.2f} seconds[/cyan]")

@app.command("narration-scenes")
def narration_scenes_command(project: str):
    """Create scene-based narration text files."""

    import time

    console.print("\n[bold cyan]🎙 Scene Narration Builder[/bold cyan]\n")
    console.print(f"[bold]📁 Project:[/bold] {project}\n")
    console.print("[yellow]⏳ Preparing scene narration files...[/yellow]")

    start = time.perf_counter()

    try:
        manifest_path = NarrationBuilder().build(project)
    except Exception as error:
        console.print(
            "\n[bold red]❌ Scene Narration Builder failed[/bold red]"
        )
        console.print(f"[red]Error: {error}[/red]")
        raise typer.Exit(code=1)

    elapsed = time.perf_counter() - start

    console.print(
        "\n[bold green]✅ Scene narration files created[/bold green]"
    )
    console.print(f"[bold]📄 Manifest:[/bold] {manifest_path}")
    console.print(
        f"[cyan]⏱ Completed in {elapsed:.2f} seconds[/cyan]"
    )

@app.command("voice")
def voice_command(
    project: str,
    provider: str = "espeak",
    speed: int = 145,
):
    """Generate scene narration audio files."""

    import time

    console.print("\n[bold cyan]🎙 Voice Generator[/bold cyan]\n")
    console.print(f"[bold]📁 Project:[/bold] {project}")
    console.print(f"[bold]🔊 Provider:[/bold] {provider}")
    console.print(f"[bold]⚡ Speed:[/bold] {speed}\n")
    console.print("[yellow]⏳ Generating scene audio...[/yellow]\n")

    start = time.perf_counter()

    try:
        manifest_path = VoiceService().generate(
            project,
            provider_key=provider,
            speed=speed,
        )
    except Exception as error:
        console.print("\n[bold red]❌ Voice generation failed[/bold red]")
        console.print(f"[red]Error: {error}[/red]")
        raise typer.Exit(code=1)

    elapsed = time.perf_counter() - start

    console.print("\n[bold green]✅ Scene audio generated[/bold green]")
    console.print(f"[bold]📄 Manifest:[/bold] {manifest_path}")
    console.print(f"[cyan]⏱ Completed in {elapsed:.2f} seconds[/cyan]")

def main():
    app()


if __name__ == "__main__":
    main()
