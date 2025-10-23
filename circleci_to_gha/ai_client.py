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
        self.model = "gemini-2.5-pro"
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
            max_output_tokens=65536,  # Maximum supported by Gemini 2.5
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
        """Generate GitHub Actions workflows.

        Uses a strategy to avoid token limits:
        - If config is small, generate all workflows at once
        - If config is large, parse workflows and generate one at a time
        """
        import yaml

        # Try to parse the config to extract individual workflows
        try:
            config_data = yaml.safe_load(circleci_config)
            workflows_section = config_data.get("workflows", {})

            # If we have multiple workflows defined, generate them one at a time
            if workflows_section and len(workflows_section) > 1:
                return self._generate_workflows_individually(circleci_config, config_data)
        except:
            pass  # If parsing fails, fall back to generating all at once

        # Default: generate all workflows at once
        return self._generate_all_workflows(circleci_config)

    def _generate_all_workflows(self, circleci_config: str) -> dict[str, str]:
        """Generate all workflows in a single AI call."""
        examples = self._load_examples()
        prompt = f"""Convert this CircleCI configuration to GitHub Actions workflows.

MOST IMPORTANT RULE - READ THIS FIRST:
When you see a 'run:' or 'command:' in CircleCI, you MUST copy the ENTIRE command to GitHub Actions.
COUNT the lines in each CircleCI command and ensure the same number appears in GitHub Actions.
NEVER write "run: |" followed by nothing or fewer lines than the original.
This is the #1 priority - complete commands are more important than anything else.

SPECIAL ATTENTION TO CURL AND MULTI-LINE COMMANDS:
- Curl commands with backslash line continuations (\) MUST include ALL lines
- If CircleCI has: curl -X POST \ -H "header" \ -d "data" URL
- GitHub Actions MUST have: curl -X POST \ -H "header" \ -d "data" URL (all lines)
- NEVER truncate curl commands - copy every single line including all headers, data, and the URL
- Multi-line bash scripts with pipes (|) MUST be copied completely

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

CRITICAL REQUIREMENTS:

1. COPY ALL COMMAND LINES:
   - Look at EACH 'run:' or 'command:' in CircleCI
   - Count how many lines of bash/shell code it has
   - Copy ALL those lines to the GitHub Actions 'run:' field
   - If you copy fewer lines, the migration is BROKEN

2. GENERATE ALL STEPS:
   - Every CircleCI step becomes a GitHub Actions step
   - If CircleCI job has 10 steps, GitHub Actions must have 10 steps
   - Never skip steps

3. COMPLETE WORKFLOWS:
   - Finish each workflow file completely
   - Don't cut off mid-file

CRITICAL OUTPUT REQUIREMENTS:
- Return ONLY valid YAML workflow files - NO commentary, explanations, or notes
- DO NOT add bullet points, markdown text, or explanations after the YAML
- DO NOT include migration notes or changes documentation in the output
- Each file should contain ONLY the workflow YAML, nothing else

NEVER GENERATE PLACEHOLDER WORKFLOWS:
- Do NOT create jobs named "placeholder" or steps with "echo 'This workflow is currently empty'"
- Do NOT create workflows with "run: echo 'TODO'" or similar placeholders
- Every job and step must be a real conversion from the CircleCI config
- You MUST convert ALL jobs and workflows - do not skip or omit any CI tasks

Return in this exact format:
FILENAME: <filename.yml>
```yaml
<complete workflow content - PURE YAML ONLY>
```

FILENAME: <next-file.yml>
```yaml
<complete workflow content - PURE YAML ONLY>
```

Generate one workflow file per CircleCI workflow. Be consistent and deterministic.
NO TEXT OR COMMENTARY AFTER THE YAML CODE BLOCKS.
"""
        response = self._call_gemini(prompt)
        workflows = self._parse_workflows(response)

        # Validate each workflow for completeness
        import sys
        for filename, content in workflows.items():
            warnings = self._validate_workflow_completeness(filename, content)
            for warning in warnings:
                print(warning, file=sys.stderr)

        return workflows

    def _generate_workflows_individually(self, circleci_config: str, config_data: dict) -> dict[str, str]:
        """Generate each workflow separately to avoid token limits.

        This method generates one GitHub Actions workflow at a time by focusing
        on each CircleCI workflow individually, which helps stay within token limits.

        Args:
            circleci_config: Full CircleCI config (unused but kept for signature consistency)
            config_data: Parsed CircleCI config data
        """
        import yaml
        import sys

        # Note: circleci_config parameter is unused - we work with parsed config_data instead
        _ = circleci_config  # Explicitly mark as intentionally unused

        all_workflows = {}
        workflows_section = config_data.get("workflows", {})
        jobs_section = config_data.get("jobs", {})

        # Filter out version key - it's not a workflow, just CircleCI metadata
        actual_workflows = {k: v for k, v in workflows_section.items() if k != "version"}

        if not actual_workflows:
            print("No actual workflows found in config", file=sys.stderr)
            return {}

        print(f"Detected {len(actual_workflows)} workflows - generating individually to avoid token limits...", file=sys.stderr)

        for workflow_name, workflow_config in actual_workflows.items():
            print(f"  Generating workflow: {workflow_name}...", file=sys.stderr)

            # Create a minimal config with just this workflow and its referenced jobs
            referenced_jobs = set()
            if isinstance(workflow_config, dict) and "jobs" in workflow_config:
                for job_entry in workflow_config["jobs"]:
                    if isinstance(job_entry, dict):
                        job_name = list(job_entry.keys())[0]
                        referenced_jobs.add(job_name)
                    else:
                        referenced_jobs.add(job_entry)

            # Build minimal config with only this workflow
            minimal_config = {
                "version": config_data.get("version", 2.1),
                "orbs": config_data.get("orbs", {}),
                "jobs": {job: jobs_section[job] for job in referenced_jobs if job in jobs_section},
                "workflows": {workflow_name: workflow_config}
            }

            minimal_yaml = yaml.dump(minimal_config, default_flow_style=False, sort_keys=False)

            # Generate this single workflow
            examples = self._load_examples()
            prompt = f"""Convert this CircleCI workflow to a GitHub Actions workflow.

MOST IMPORTANT RULE - READ THIS FIRST:
When you see a 'run:' or 'command:' in CircleCI, you MUST copy the ENTIRE command to GitHub Actions.
COUNT the lines in each CircleCI command and ensure the same number appears in GitHub Actions.
NEVER write "run: |" followed by nothing or fewer lines than the original.
This is the #1 priority - complete commands are more important than anything else.

SPECIAL ATTENTION TO CURL AND MULTI-LINE COMMANDS:
- Curl commands with backslash line continuations (\) MUST include ALL lines
- If CircleCI has: curl -X POST \ -H "header" \ -d "data" URL
- GitHub Actions MUST have: curl -X POST \ -H "header" \ -d "data" URL (all lines)
- NEVER truncate curl commands - copy every single line including all headers, data, and the URL
- Multi-line bash scripts with pipes (|) MUST be copied completely

Here are some examples of successful migrations to follow:

{examples}

Now convert this CircleCI workflow:

CircleCI Config (single workflow):
```yaml
{minimal_yaml}
```

IMPORTANT INSTRUCTIONS:
1. Generate complete, production-ready GitHub Actions workflow YAML file
2. Follow the exact patterns shown in the examples above
3. Use OIDC authentication (never API tokens or credentials)
4. For PyPI publishing: NEVER use twine - only use pypa/gh-action-pypi-publish@release/v1
5. For Docker: Use mozilla-it/deploy-actions/docker-push@v4.3.2
6. For ID tokens: Use token_format: 'id_token' and export GOOGLE_GHA_ID_TOKEN
7. Preserve all job dependencies and workflow logic from CircleCI
8. Use consistent naming: match CircleCI job names where possible

CRITICAL REQUIREMENTS:

1. COPY ALL COMMAND LINES:
   - Look at EACH 'run:' or 'command:' in CircleCI
   - Count how many lines of bash/shell code it has
   - Copy ALL those lines to the GitHub Actions 'run:' field
   - If you copy fewer lines, the migration is BROKEN

2. GENERATE ALL STEPS:
   - Every CircleCI step becomes a GitHub Actions step
   - If CircleCI job has 10 steps, GitHub Actions must have 10 steps
   - Never skip steps

3. COMPLETE WORKFLOWS:
   - Finish each workflow file completely
   - Don't cut off mid-file

CRITICAL OUTPUT REQUIREMENTS:
- Return ONLY valid YAML workflow file - NO commentary, explanations, or notes
- DO NOT add bullet points, markdown text, or explanations after the YAML
- DO NOT include migration notes or changes documentation in the output
- The file should contain ONLY the workflow YAML, nothing else

NEVER GENERATE PLACEHOLDER WORKFLOWS:
- Do NOT create jobs named "placeholder" or steps with "echo 'This workflow is currently empty'"
- Do NOT create workflows with "run: echo 'TODO'" or similar placeholders
- Every job and step must be a real conversion from the CircleCI config
- You MUST convert ALL jobs and workflows - do not skip or omit any CI tasks

Return in this exact format:
FILENAME: {workflow_name}.yml
```yaml
<complete workflow content - PURE YAML ONLY>
```

Generate one complete workflow file. Be consistent and deterministic.
NO TEXT OR COMMENTARY AFTER THE YAML CODE BLOCK.
"""

            response = self._call_gemini(prompt)
            workflow_files = self._parse_workflows(response)

            # Validate this workflow
            for filename, content in workflow_files.items():
                warnings = self._validate_workflow_completeness(filename, content)
                for warning in warnings:
                    print(warning, file=sys.stderr)

            all_workflows.update(workflow_files)

        return all_workflows

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

        Strips any non-YAML content (commentary, notes, etc.)
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
                    content = self._clean_yaml_content(current_content)
                    if content:  # Only save if there's actual content
                        workflows[current_file] = content

                # Extract new filename
                current_file = line.replace("FILENAME:", "").strip()
                current_content = []
                in_code_block = False

            elif line.startswith("```yaml") or line.startswith("```yml"):
                in_code_block = True

            elif line.startswith("```") and in_code_block:
                # End of code block - stop capturing
                in_code_block = False
                # Don't capture anything after the code block ends

            elif current_file and in_code_block:
                # Only capture content inside code blocks
                current_content.append(line)

            i += 1

        # Save last workflow
        if current_file and current_content:
            content = self._clean_yaml_content(current_content)
            if content:
                workflows[current_file] = content

        return workflows

    def _clean_yaml_content(self, lines: list[str]) -> str:
        """Clean and validate YAML content.

        Removes any non-YAML lines like markdown bullet points or commentary.
        """
        cleaned_lines = []
        for line in lines:
            # Skip lines that look like markdown/commentary
            stripped = line.strip()
            if stripped.startswith(("*", "-", "•")) and ":" not in line:
                # Skip markdown bullet points (unless they're YAML list items with colons)
                continue
            if stripped.startswith("#") and not line.startswith("#"):
                # Skip markdown headings (but keep YAML comments)
                continue

            cleaned_lines.append(line)

        # Join and strip whitespace
        content = "\n".join(cleaned_lines).strip()

        # Remove any trailing commentary after the last YAML line
        # Look for the last line that looks like YAML
        lines_list = content.split("\n")
        last_yaml_idx = len(lines_list) - 1

        for i in range(len(lines_list) - 1, -1, -1):
            line = lines_list[i].strip()
            if line and not line.startswith(("*", "-", "•", "**")):
                # Found a line that might be YAML
                if ":" in line or line.startswith("-") or not line:
                    last_yaml_idx = i
                    break

        # Only keep content up to last YAML line
        if last_yaml_idx < len(lines_list) - 1:
            content = "\n".join(lines_list[:last_yaml_idx + 1])

        return content.strip()

    def _validate_workflow_completeness(self, filename: str, content: str) -> list[str]:
        """Validate that workflow content is complete and not truncated.

        Returns list of warnings if issues are detected.
        """
        warnings = []
        lines = content.strip().split("\n")

        if not lines:
            warnings.append(f"⚠️  {filename}: Workflow is empty")
            return warnings

        last_line = lines[-1].strip()

        # Check for incomplete steps (common signs of truncation)
        truncation_indicators = [
            "...",  # Ellipsis indicating continuation
            "# TODO",  # Placeholder comments
            "# ...",  # Comment ellipsis
            "# rest of",  # "# rest of script"
            "# remaining",  # "# remaining commands"
        ]

        for indicator in truncation_indicators:
            if indicator in last_line:
                warnings.append(
                    f"⚠️  {filename}: Workflow may be incomplete - ends with '{indicator}'"
                )

        # Check for unclosed structures
        indent_level = len(last_line) - len(last_line.lstrip())
        if indent_level > 2:  # Deep indentation suggests we're mid-structure
            warnings.append(
                f"⚠️  {filename}: Workflow may be incomplete - ends with deep indentation"
            )

        # Check if last line looks like it's mid-definition
        if last_line.endswith(":"):
            warnings.append(
                f"⚠️  {filename}: Workflow may be incomplete - ends with colon (incomplete definition)"
            )

        # Check for empty or suspiciously short run commands
        in_run_block = False
        run_line_number = 0
        run_content_lines = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Detect start of run block
            if stripped.startswith("run:"):
                in_run_block = True
                run_line_number = i
                run_content_lines = 0

                # Check if it's a single-line run
                if len(stripped) > 5 and not stripped.endswith(("|", ">")):
                    in_run_block = False  # Single line run, not a block

            elif in_run_block:
                # Check if we're still in the run block (indented further than 'run:')
                if line and not line[0].isspace():
                    # We've left the run block
                    if run_content_lines == 0:
                        warnings.append(
                            f"⚠️  {filename}:{run_line_number} - Empty 'run:' command with no script content"
                        )
                    in_run_block = False
                elif stripped and not stripped.startswith("#"):
                    # Count non-empty, non-comment lines in run block
                    run_content_lines += 1
                elif stripped == "" and run_content_lines == 0:
                    # Empty line immediately after run: | suggests missing content
                    # But wait for next line to confirm
                    pass

        # Try basic YAML validation
        try:
            import yaml
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            error_msg = str(e).split("\n")[0]  # First line of error
            warnings.append(f"⚠️  {filename}: YAML validation error - {error_msg}")

        return warnings


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