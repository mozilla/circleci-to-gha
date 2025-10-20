"""CLI interface for CircleCI to GitHub Actions migration."""

import click
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from dotenv import load_dotenv

from .config_parser import parse_circleci_config
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
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default=".circleci/config.yml",
    help="Path to CircleCI config file",
)
@click.option(
    "--provider",
    type=click.Choice(["claude", "gemini"]),
    default="claude",
    help="AI provider to use",
)
def analyze(config: Path, provider: str):
    """Analyze CircleCI config and generate migration plan."""
    console.print(f"[bold blue]Analyzing {config}...[/bold blue]")
    
    # Parse CircleCI config
    circleci_config = parse_circleci_config(config)
    
    # Get AI analysis
    ai_client = get_ai_client(provider)
    analysis = ai_client.analyze_config(circleci_config)
    
    console.print("\n[bold green]Migration Analysis:[/bold green]")
    console.print(Markdown(analysis))


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default=".circleci/config.yml",
    help="Path to CircleCI config file",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=".github/workflows",
    help="Output directory for GitHub Actions workflows",
)
@click.option(
    "--provider",
    type=click.Choice(["claude", "gemini"]),
    default="claude",
    help="AI provider to use",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show generated workflows without saving",
)
def generate(config: Path, output: Path, provider: str, dry_run: bool):
    """Generate GitHub Actions workflows from CircleCI config."""
    console.print(f"[bold blue]Generating workflows from {config}...[/bold blue]")
    
    # Parse CircleCI config
    circleci_config = parse_circleci_config(config)
    
    # Generate workflows using AI
    ai_client = get_ai_client(provider)
    workflows = generate_workflows(ai_client, circleci_config)
    
    if dry_run:
        console.print("\n[bold yellow]Generated Workflows (dry-run):[/bold yellow]")
        for name, content in workflows.items():
            console.print(f"\n[bold]{name}[/bold]")
            console.print(Markdown(f"```yaml\n{content}\n```"))
    else:
        save_workflows(workflows, output)
        console.print(f"\n[bold green]✓ Workflows saved to {output}[/bold green]")


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default=".circleci/config.yml",
    help="Path to CircleCI config file",
)
@click.option(
    "--provider",
    type=click.Choice(["claude", "gemini"]),
    default="claude",
    help="AI provider to use",
)
def checklist(config: Path, provider: str):
    """Generate migration checklist including infrastructure changes."""
    console.print(f"[bold blue]Generating migration checklist...[/bold blue]")
    
    circleci_config = parse_circleci_config(config)
    ai_client = get_ai_client(provider)
    
    checklist = ai_client.generate_checklist(circleci_config)
    
    console.print("\n[bold green]Migration Checklist:[/bold green]")
    console.print(Markdown(checklist))


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

