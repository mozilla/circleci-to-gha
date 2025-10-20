"""CLI interface for CircleCI to GitHub Actions migration."""

import click
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from dotenv import load_dotenv

from .config_parser import parse_circleci_config, discover_circleci_configs, extract_config_metadata
from .ai_client import get_ai_client
from .generator import generate_workflows, save_workflows, normalize_filename

load_dotenv()
console = Console()


def display_detected_requirements(metadata: dict) -> None:
    """Display detected special requirements from config metadata."""
    if metadata["has_dryrun"]:
        console.print("[bold yellow]ℹ️  Detected dryrun/SQL validation patterns[/bold yellow]")
        console.print("   This workflow will need:")
        console.print("   • GCP_DRYRUN_SERVICE_ACCOUNT_EMAIL secret")
        console.print("   • ID token authentication for Cloud Functions")
        console.print("   • GOOGLE_GHA_ID_TOKEN environment variable export")
        console.print()

    if metadata["has_docker"]:
        console.print("[bold yellow]ℹ️  Detected Docker builds[/bold yellow]")
        console.print("   This will require a dataservices-infra PR for GAR access")
        console.print()


def display_workflow_list(workflows: dict) -> None:
    """Display the list of generated workflow files."""
    console.print(f"[bold cyan]📝 Generated {len(workflows)} workflow file(s):[/bold cyan]")
    for filename in sorted(workflows.keys()):
        console.print(f"   • {filename}")


def display_workflow_content(workflows: dict, mode: str = "preview") -> None:
    """Display workflow YAML content.

    Args:
        workflows: Dictionary of filename -> content
        mode: Either "preview" or "saved"
    """
    if mode == "preview":
        header = "\n[bold yellow]Workflow Content (preview - not saved):[/bold yellow]"
    else:
        header = "\n[bold green]Saved Workflow Content:[/bold green]"

    console.print(header)
    for name, content in sorted(workflows.items()):
        console.print(f"\n[bold cyan]{'─' * 80}[/bold cyan]")
        console.print(f"[bold cyan]File: {name}[/bold cyan]")
        console.print(f"[bold cyan]{'─' * 80}[/bold cyan]")
        console.print(Markdown(f"```yaml\n{content}\n```"))


@click.group()
@click.version_option()
def cli():
    """Mozilla CircleCI to GitHub Actions Migration Assistant."""
    pass


@cli.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
    help="Path to repository to migrate (default: current directory)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory for GitHub Actions workflows (default: repo/.github/workflows)",
)
@click.option(
    "--project-id",
    envvar="GOOGLE_CLOUD_PROJECT",
    required=True,
    help="Google Cloud Project ID",
    default="mozdata"
)
@click.option(
    "--location",
    envvar="GOOGLE_CLOUD_LOCATION",
    default="global",
    help="Google Cloud Location",
)
@click.option(
    "--write/--no-write",
    default=True,
    help="Write generated workflows to files (default: write)",
)
@click.option(
    "--remove-circleci",
    is_flag=True,
    help="Remove CircleCI config directory after generating workflows",
)
def migrate(repo: Path, output: Path, project_id: str, location: str, write: bool, remove_circleci: bool):
    """Analyze and generate GitHub Actions workflows in one step (recommended)."""
    try:
        # Discover CircleCI configs
        configs = discover_circleci_configs(repo)

        if len(configs) > 1:
            console.print(f"[bold yellow]Found {len(configs)} CircleCI configs:[/bold yellow]")
            for i, config in enumerate(configs, 1):
                console.print(f"  {i}. {config.name}")
            console.print()

        # Get AI client once for all operations
        ai_client = get_ai_client(project_id=project_id, location=location)

        for config in configs:
            console.print(f"\n[bold blue]{'='*80}[/bold blue]")
            console.print(f"[bold blue]Processing {config.name}[/bold blue]")
            console.print(f"[bold blue]{'='*80}[/bold blue]\n")

            # Extract metadata to detect special requirements
            metadata = extract_config_metadata(config)
            display_detected_requirements(metadata)

            # Parse CircleCI config
            circleci_config = parse_circleci_config(config)

            # Step 1: Analyze
            console.print(f"[bold cyan]📊 Analyzing {config.name}...[/bold cyan]")
            analysis = ai_client.analyze_config(circleci_config)
            console.print(f"\n[bold green]Migration Analysis:[/bold green]")
            console.print(Markdown(analysis))
            console.print()

            # Step 2: Generate workflows
            console.print(f"[bold cyan]⚙️  Generating workflows from {config.name}...[/bold cyan]")
            workflows = generate_workflows(ai_client, circleci_config)

            # Debug: show original filenames from AI
            import os
            if os.environ.get("DEBUG_FILENAMES"):
                console.print("[dim]Debug - Original filenames from AI:[/dim]")
                for orig_name in workflows.keys():
                    console.print(f"[dim]  {orig_name} -> {normalize_filename(orig_name)}[/dim]")

            # Normalize filenames for consistent display
            normalized_workflows = {normalize_filename(name): content for name, content in workflows.items()}

            # Always show what workflow files will be created
            display_workflow_list(normalized_workflows)

            if not write:
                # Preview mode - show content without saving
                display_workflow_content(normalized_workflows, mode="preview")
            else:
                # Write mode - save files and show what was saved
                if output is None:
                    output_dir = repo.resolve() / ".github" / "workflows"
                else:
                    output_dir = output

                # Save and get back what was actually saved
                saved_workflows = save_workflows(workflows, output_dir)
                console.print(f"[bold green]✓ Workflows saved to {output_dir}[/bold green]")

                # Verify what was saved matches what we showed
                if set(saved_workflows.keys()) != set(normalized_workflows.keys()):
                    console.print("[bold yellow]⚠️  Warning: Saved filenames differ from generated[/bold yellow]")

                # Show the content that was saved
                display_workflow_content(saved_workflows, mode="saved")

            console.print()

        # Remove CircleCI config if requested
        if remove_circleci and write:
            import shutil
            circleci_dir = repo.resolve() / ".circleci"
            if circleci_dir.exists():
                try:
                    shutil.rmtree(circleci_dir)
                    console.print(f"\n[bold green]✓ Removed CircleCI config directory: {circleci_dir}[/bold green]")
                except OSError as e:
                    console.print(f"[bold red]✗ Failed to remove CircleCI directory: {e}[/bold red]")

        console.print(f"\n[bold green]{'='*80}[/bold green]")
        console.print(f"[bold green]✓ Migration complete![/bold green]")
        console.print(f"[bold green]{'='*80}[/bold green]")

    except FileNotFoundError as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise click.Abort()


@cli.command()
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=".",
    help="Path to repository to migrate (default: current directory)",
)
@click.option(
    "--project-id",
    envvar="GOOGLE_CLOUD_PROJECT",
    required=True,
    help="Google Cloud Project ID",
    default="mozdata"
)
@click.option(
    "--location",
    envvar="GOOGLE_CLOUD_LOCATION",
    default="global",
    help="Google Cloud Location",
)
def checklist(repo: Path, project_id: str, location: str):
    """Generate migration checklist including infrastructure changes using Gemini."""
    try:
        # Discover CircleCI configs
        configs = discover_circleci_configs(repo)

        if len(configs) > 1:
            console.print(f"[bold yellow]Found {len(configs)} CircleCI configs:[/bold yellow]")
            for i, config in enumerate(configs, 1):
                console.print(f"  {i}. {config.name}")
            console.print()

        # Generate checklist for each config
        ai_client = get_ai_client(project_id=project_id, location=location)

        for config in configs:
            console.print(f"[bold blue]Generating migration checklist for {config.name}...[/bold blue]")

            circleci_config = parse_circleci_config(config)
            checklist_content = ai_client.generate_checklist(circleci_config)

            console.print(f"\n[bold green]Migration Checklist for {config.name}:[/bold green]")
            console.print(Markdown(checklist_content))
            console.print("\n" + "="*80 + "\n")

    except FileNotFoundError as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise click.Abort()


if __name__ == "__main__":
    cli()

