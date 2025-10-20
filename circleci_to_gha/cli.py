"""CLI interface for CircleCI to GitHub Actions migration."""

import click
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from dotenv import load_dotenv

from .config_parser import parse_circleci_config, discover_circleci_configs
from .ai_client import get_ai_client
from .generator import generate_workflows, save_workflows

load_dotenv()
console = Console()


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
def analyze(repo: Path, project_id: str, location: str):
    """Analyze CircleCI config and generate migration plan using Gemini."""
    try:
        # Discover CircleCI configs
        configs = discover_circleci_configs(repo)

        if len(configs) > 1:
            console.print(f"[bold yellow]Found {len(configs)} CircleCI configs:[/bold yellow]")
            for i, config in enumerate(configs, 1):
                console.print(f"  {i}. {config.name}")
            console.print()

        # Analyze each config
        ai_client = get_ai_client(project_id=project_id, location=location)

        for config in configs:
            console.print(f"[bold blue]Analyzing {config.name}...[/bold blue]")

            # Parse CircleCI config
            circleci_config = parse_circleci_config(config)

            # Get AI analysis
            analysis = ai_client.analyze_config(circleci_config)

            console.print(f"\n[bold green]Migration Analysis for {config.name}:[/bold green]")
            console.print(Markdown(analysis))
            console.print("\n" + "="*80 + "\n")

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
    "--dry-run",
    is_flag=True,
    help="Show generated workflows without saving",
)
@click.option(
    "--remove-circleci",
    is_flag=True,
    help="Remove CircleCI config directory after generating workflows",
)
def generate(repo: Path, output: Path, project_id: str, location: str, dry_run: bool, remove_circleci: bool):
    """Generate GitHub Actions workflows from CircleCI config using Gemini."""
    try:
        # Discover CircleCI configs
        configs = discover_circleci_configs(repo)

        if len(configs) > 1:
            console.print(f"[bold yellow]Found {len(configs)} CircleCI configs:[/bold yellow]")
            for i, config in enumerate(configs, 1):
                console.print(f"  {i}. {config.name}")
            console.print()

        # Generate workflows using AI
        ai_client = get_ai_client(project_id=project_id, location=location)

        for config in configs:
            console.print(f"[bold blue]Generating workflows from {config.name}...[/bold blue]")

            # Parse CircleCI config
            circleci_config = parse_circleci_config(config)

            # Generate workflows
            workflows = generate_workflows(ai_client, circleci_config)

            if dry_run:
                console.print(f"\n[bold yellow]Generated Workflows from {config.name} (dry-run):[/bold yellow]")
                for name, content in workflows.items():
                    console.print(f"\n[bold]{name}[/bold]")
                    console.print(Markdown(f"```yaml\n{content}\n```"))
            else:
                # If output not specified, determine it from repo path
                if output is None:
                    output = repo.resolve() / ".github" / "workflows"

                save_workflows(workflows, output)
                console.print(f"\n[bold green]✓ Workflows from {config.name} saved to {output}[/bold green]")
                for filename in workflows.keys():
                    console.print(f"  - {Path(filename).name}")

            console.print()

        # Remove CircleCI config if requested
        if remove_circleci and not dry_run:
            import shutil
            circleci_dir = repo.resolve() / ".circleci"
            if circleci_dir.exists():
                try:
                    shutil.rmtree(circleci_dir)
                    console.print(f"[bold green]✓ Removed CircleCI config directory: {circleci_dir}[/bold green]")
                except OSError as e:
                    console.print(f"[bold red]✗ Failed to remove CircleCI directory: {e}[/bold red]")

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


@cli.command()
@click.argument("repo-name")
def infra_pr(repo_name: str):
    """Generate dataservices-infra PR content for GAR access."""
    console.print(f"[bold blue]Generating infra PR for {repo_name}...[/bold blue]")
    
    pr_content = f"""## Add GAR access for {repo_name}

This PR adds the `{repo_name}` repository to the list of repositories 
that can push images to Google Artifact Registry.

### Changes
- Added `{repo_name}` to the repository list in `data-artifacts/tf/prod/locals.tf`

### Testing
- [ ] Terraform plan shows expected changes
- [ ] No other resources affected

Related to CircleCI → GitHub Actions migration.
"""
    
    console.print(Markdown(pr_content))
    
    # Save to file
    pr_file = Path("infra-pr-content.md")
    pr_file.write_text(pr_content)
    console.print(f"\n[bold green]✓ PR content saved to {pr_file}[/bold green]")


if __name__ == "__main__":
    cli()

