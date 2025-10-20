"""AI client for Gemini."""

import os
from pathlib import Path


class GeminiClient:
    """Gemini AI client using Vertex AI."""

    def __init__(self, project_id: str, location: str = "global"):
        from google import genai
        from google.genai.types import HttpOptions

        # Set environment variables for Vertex AI
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
        os.environ["GOOGLE_CLOUD_LOCATION"] = location
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

        # Create client with Vertex AI configuration
        self.client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            http_options=HttpOptions(api_version="v1")
        )
        self.model = "gemini-2.0-flash-exp"
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Load system prompt from file."""
        prompt_path = Path(__file__).parent / "prompts" / "system_prompt.txt"
        return prompt_path.read_text()

    def _load_examples(self) -> str:
        """Load examples from file."""
        examples_path = Path(__file__).parent / "prompts" / "examples.txt"
        return examples_path.read_text()

    def _call_gemini(self, user_message: str) -> str:
        """Make API call to Gemini with consistent generation config."""
        from google.genai import types

        full_prompt = f"{self.system_prompt}\n\n{user_message}"

        # Use lower temperature for more consistent, deterministic outputs
        generation_config = types.GenerateContentConfig(
            temperature=0.1,  # Low temperature for consistency (0.0-1.0)
            top_p=0.95,       # Nucleus sampling
            top_k=40,         # Top-k sampling
            max_output_tokens=8192,
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config=generation_config,
        )
        return response.text

    def analyze_config(self, circleci_config: str) -> str:
        """Analyze CircleCI config."""
        prompt = f"""Analyze this CircleCI configuration and provide a migration plan to GitHub Actions.

CircleCI Config:
```yaml
{circleci_config}
```

Provide a focused analysis including:
1. **Required Secrets** - List all GitHub repository secrets needed
2. **Infrastructure Changes** - Any dataservices-infra PRs needed (for Docker/GAR access, Airflow triggers, etc.)
3. **Key Migration Points** - Important patterns to migrate (Docker, GCP auth, PyPI publishing, etc.)
4. **Manual Verification Steps** - What to check after migration

DO NOT list specific workflow filenames - those will be generated and shown separately.
Focus on what needs to be configured and verified, not the file structure.
"""
        return self._call_gemini(prompt)

    def generate_workflow(self, circleci_config: str) -> dict[str, str]:
        """Generate GitHub Actions workflows."""
        examples = self._load_examples()
        prompt = f"""Convert this CircleCI configuration to GitHub Actions workflows.

Here are some examples of successful migrations to follow:

{examples}

Now convert this CircleCI configuration:

CircleCI Config:
```yaml
{circleci_config}
```

IMPORTANT INSTRUCTIONS:
1. Generate complete, production-ready GitHub Actions workflow YAML files
2. Follow the exact patterns shown in the examples above
3. Use OIDC authentication (never API tokens or credentials)
4. For PyPI publishing: NEVER use twine - only use pypa/gh-action-pypi-publish@release/v1
5. For Docker: Use mozilla-it/deploy-actions/docker-push@v4.3.2
6. For ID tokens: Use token_format: 'id_token' and export GOOGLE_GHA_ID_TOKEN
7. Preserve all job dependencies and workflow logic from CircleCI
8. Use consistent naming: match CircleCI job names where possible

Return in this exact format:
FILENAME: <filename.yml>
```yaml
<complete workflow content>
```

Generate one workflow file per CircleCI workflow. Be consistent and deterministic.
"""
        response = self._call_gemini(prompt)
        return self._parse_workflows(response)


    def generate_checklist(self, circleci_config: str) -> str:
        """Generate migration checklist."""
        prompt = f"""Create a detailed migration checklist for converting this CircleCI config to GitHub Actions.

CircleCI Config:
```yaml
{circleci_config}
```
Include:
- Repository secrets to configure
- Infrastructure changes needed (dataservices-infra PR)
- Workflow files to create
- Manual verification steps
"""

        return self._call_gemini(prompt)

    def _parse_workflows(self, response: str) -> dict[str, str]:
        """Parse workflow files from AI response.

        Supports multiple formats:
        - FILENAME: name.yml followed by ```yaml code block
        - FILENAME: name.yml followed by raw YAML
        """
        workflows = {}
        lines = response.split("\n")
        current_file = None
        current_content = []
        in_code_block = False

        i = 0
        while i < len(lines):
            line = lines[i]

            if line.startswith("FILENAME:"):
                # Save previous workflow if exists
                if current_file and current_content:
                    # Clean up content - remove empty lines from start/end
                    content = "\n".join(current_content).strip()
                    workflows[current_file] = content

                # Extract new filename
                current_file = line.replace("FILENAME:", "").strip()
                current_content = []
                in_code_block = False

            elif line.startswith("```yaml") or line.startswith("```yml"):
                in_code_block = True

            elif line.startswith("```") and in_code_block:
                in_code_block = False

            elif current_file:
                # If we're in a code block, or if there's no code block yet, capture content
                if in_code_block or (not any(l.startswith("```") for l in lines[max(0, i-5):i])):
                    current_content.append(line)

            i += 1

        # Save last workflow
        if current_file and current_content:
            content = "\n".join(current_content).strip()
            workflows[current_file] = content

        return workflows


def get_ai_client(project_id: str, location: str = "global") -> GeminiClient:
    """Factory function to get Gemini AI client using Vertex AI.

    Args:
        project_id: Google Cloud Project ID
        location: Google Cloud Location (default: "global")

    Returns:
        GeminiClient instance configured for Vertex AI

    Raises:
        Exception: If authentication or configuration fails
    """
    return GeminiClient(project_id=project_id, location=location)