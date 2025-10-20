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


def normalize_filename(filename: str) -> str:
    """Normalize workflow filename.

    Args:
        filename: Original filename from AI

    Returns:
        Normalized filename (basename with .yml extension)
    """
    # Strip any leading path components (AI might include .github/workflows/)
    filename = Path(filename).name

    # Ensure .yml extension
    if not filename.endswith((".yml", ".yaml")):
        filename = f"{filename}.yml"

    return filename


def save_workflows(workflows: Dict[str, str], output_dir: Path) -> Dict[str, str]:
    """Save generated workflows to disk.

    Args:
        workflows: Dictionary mapping filenames to workflow content
        output_dir: Directory to save workflow files

    Returns:
        Dictionary mapping normalized filenames to workflow content (what was actually saved)

    Raises:
        OSError: If directory creation or file writing fails
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise OSError(f"Failed to create output directory {output_dir}: {e}")

    saved_workflows = {}

    for original_filename, content in workflows.items():
        # Normalize the filename
        filename = normalize_filename(original_filename)

        filepath = output_dir / filename
        try:
            filepath.write_text(content)
            saved_workflows[filename] = content
        except OSError as e:
            raise OSError(f"Failed to write workflow file {filepath}: {e}")

    return saved_workflows
        