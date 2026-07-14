import typer

from app.core.config import settings

app = typer.Typer(
    no_args_is_help=True,
    help="AI-powered documentary production platform.",
)


@app.command("version")
def version_command():
    """Show version information."""
    typer.echo(settings.project_name)
    typer.echo(f"Version: {settings.version}")
    typer.echo("Status: Ready")


@app.command("generate")
def generate_command(topic: str):
    """Generate a new documentary project."""

    from app.cli.generate import generate

    project_dir = generate(topic)

    typer.echo(f"✅ Project created: {project_dir}")

def main():
    app()


if __name__ == "__main__":
    main()
