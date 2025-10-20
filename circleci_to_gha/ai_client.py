"""AI client abstraction for Claude and Gemini."""

import os
from abc import ABC, abstractmethod
from pathlib import Path


class AIClient(ABC):
    """Abstract AI client interface."""
    
    @abstractmethod
    def analyze_config(self, circleci_config: str) -> str:
        """Analyze CircleCI config and return migration plan."""
        pass
    
    @abstractmethod
    def generate_workflow(self, circleci_config: str) -> dict[str, str]:
        """Generate GitHub Actions workflows."""
        pass
    
    @abstractmethod
    def generate_checklist(self, circleci_config: str) -> str:
        """Generate migration checklist."""
        pass


class ClaudeClient(AIClient):
    """Claude AI client."""
    
    def __init__(self):
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-3-5-sonnet-20241022"
        self.system_prompt = self._load_system_prompt()
    
    def _load_system_prompt(self) -> str:
        """Load system prompt from file."""
        prompt_path = Path(__file__).parent / "prompts" / "system_prompt.txt"
        return prompt_path.read_text()
    
    def _call_claude(self, user_message: str) -> str:
        """Make API call to Claude."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return message.content[0].text
    
    def analyze_config(self, circleci_config: str) -> str:
        """Analyze CircleCI config."""
        prompt = f"""Analyze this CircleCI configuration and provide a migration plan to GitHub Actions.

CircleCI Config:
```yaml
{circleci_config}
```
Include:

 Repository secrets to configure
 Infrastructure changes needed (dataservices-infra PR)
 Workflow files to create
 Manual verification steps
"""
        return self._call_claude(prompt)

    def generate_workflow(self, circleci_config: str) -> dict[str, str]:
        """Generate GitHub Actions workflows."""
        prompt = f"""Convert this CircleCI configuration to GitHub Actions workflows.

CircleCI Config:
```yaml
{circleci_config}
```
Generate complete GitHub Actions workflow YAML file(s).
Return in format:
FILENAME: <filename.yml>
<workflow content>
"""
        response = self._call_claude(prompt)
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
        return self._call_claude(prompt)

    def _parse_workflows(self, response: str) -> dict[str, str]:
        """Parse workflow files from AI response."""
        workflows = {}
        lines = response.split("\n")
        current_file = None
        current_content = []
        in_code_block = False

        for line in lines:
            if line.startswith("FILENAME:"):
                if current_file and current_content:
                    workflows[current_file] = "\n".join(current_content)
                current_file = line.replace("FILENAME:", "").strip()
                current_content = []
                in_code_block = False
            elif line.startswith("```yaml"):
                in_code_block = True
            elif line.startswith("```") and in_code_block:
                in_code_block = False
            elif in_code_block and current_file:
                current_content.append(line)

        if current_file and current_content:
            workflows[current_file] = "\n".join(current_content)

        return workflows


class GeminiClient(AIClient):
    """Gemini AI client."""
    def __init__(self):
        import google.generativeai as genai
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-pro")
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Load system prompt from file."""
        prompt_path = Path(__file__).parent / "prompts" / "system_prompt.txt"
        return prompt_path.read_text()

    def _call_gemini(self, user_message: str) -> str:
        """Make API call to Gemini."""
        full_prompt = f"{self.system_prompt}\n\n{user_message}"
        response = self.model.generate_content(full_prompt)
        return response.text

    def analyze_config(self, circleci_config: str) -> str:
        """Analyze CircleCI config."""
        prompt = f"""Analyze this CircleCI configuration and provide a migration plan to GitHub Actions.

CircleCI Config:
```yaml
{circleci_config}
```
Include:

 Repository secrets to configure
 Infrastructure changes needed (dataservices-infra PR)
 Workflow files to create
 Manual verification steps
"""
        return self._call_gemini(prompt)

    def generate_workflow(self, circleci_config: str) -> dict[str, str]:
        """Generate GitHub Actions workflows."""
        prompt = f"""Convert this CircleCI configuration to GitHub Actions workflows.

CircleCI Config:
```yaml
{circleci_config}
```
Generate complete GitHub Actions workflow YAML file(s).
Return in format:
FILENAME: <filename.yml>
<workflow content>
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
        """Parse workflow files from AI response."""
        workflows = {}
        lines = response.split("\n")
        current_file = None
        current_content = []
        in_code_block = False

        for line in lines:
            if line.startswith("FILENAME:"):
                if current_file and current_content:
                    workflows[current_file] = "\n".join(current_content)
                current_file = line.replace("FILENAME:", "").strip()
                current_content = []
                in_code_block = False
            elif line.startswith("```yaml"):
                in_code_block = True
            elif line.startswith("```") and in_code_block:
                in_code_block = False
            elif in_code_block and current_file:
                current_content.append(line)

        if current_file and current_content:
            workflows[current_file] = "\n".join(current_content)

        return workflows


def get_ai_client(provider: str = "claude") -> AIClient:
    """Factory function to get AI client."""
    provider = provider or os.getenv("AI_PROVIDER", "claude")
    if provider == "claude":
        return ClaudeClient()
    elif provider == "gemini":
        return GeminiClient()
    else:
        raise ValueError(f"Unknown AI provider: {provider}")