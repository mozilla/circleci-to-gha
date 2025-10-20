"""Parse CircleCI configuration files."""

import yaml
from pathlib import Path


def parse_circleci_config(config_path: Path) -> str:
    """Parse CircleCI config and return as string.

    Args:
        config_path: Path to the CircleCI configuration file

    Returns:
        Raw YAML content as a string

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is not valid YAML
    """
    with open(config_path) as f:
        raw_config = f.read()

    # Validate that it's valid YAML
    yaml.safe_load(raw_config)

    return raw_config


def extract_config_metadata(config_path: Path) -> dict:
    """Extract useful metadata from CircleCI config.

    Args:
        config_path: Path to the CircleCI configuration file

    Returns:
        Dictionary containing metadata about the configuration including:
        - has_docker: Whether Docker is used
        - has_gcp: Whether GCP/GAR is referenced
        - custom_orbs: List of custom orb names
        - jobs: List of job names
        - workflows: List of workflow names

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is not valid YAML
    """
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found: {config_path}")
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML in config file: {e}")

    metadata = {
        "has_docker": False,
        "has_gcp": False,
        "custom_orbs": [],
        "jobs": list(config.get("jobs", {}).keys()) if config else [],
        "workflows": list(config.get("workflows", {}).keys()) if config else [],
    }

    if not config:
        return metadata

    # Check for Docker
    for job in config.get("jobs", {}).values():
        if isinstance(job, dict) and "docker" in job:
            metadata["has_docker"] = True
            break

    # Check for GCP/GAR
    raw_str = str(config)
    if "gcr.io" in raw_str or "pkg.dev" in raw_str or "gcp-gcr" in raw_str:
        metadata["has_gcp"] = True

    # Extract custom orbs
    orbs = config.get("orbs", {})
    if orbs:
        metadata["custom_orbs"] = list(orbs.keys())

    return metadata
