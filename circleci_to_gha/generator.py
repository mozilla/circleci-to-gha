"""Workflow generation and file operations."""

from pathlib import Path
from typing import Dict
from .ai_client import GeminiClient


def generate_workflows(ai_client: GeminiClient, circleci_config: str) -> Dict[str, str]:
    """Generate GitHub Actions workflows using Gemini AI.

    Args:
        ai_client: Gemini AI client instance
        circleci_config: Raw CircleCI configuration as string

    Returns:
        Dictionary mapping workflow filenames to their YAML content

    Raises:
        Exception: If AI client fails to generate workflows
    """
    return ai_client.generate_workflow(circleci_config)


def save_workflows(workflows: Dict[str, str], output_dir: Path) -> None:
    """Save generated workflows to disk.

    Args:
        workflows: Dictionary mapping filenames to workflow content
        output_dir: Directory to save workflow files

    Raises:
        OSError: If directory creation or file writing fails
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise OSError(f"Failed to create output directory {output_dir}: {e}")

    for filename, content in workflows.items():
        # Strip any leading path components (AI might include .github/workflows/)
        filename = Path(filename).name

        # Ensure .yml extension
        if not filename.endswith((".yml", ".yaml")):
            filename = f"{filename}.yml"

        filepath = output_dir / filename
        try:
            filepath.write_text(content)
        except OSError as e:
            raise OSError(f"Failed to write workflow file {filepath}: {e}")
        