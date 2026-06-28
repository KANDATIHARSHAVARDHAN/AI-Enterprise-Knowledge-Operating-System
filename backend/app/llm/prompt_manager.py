"""
EKOS Prompt Manager
Loads, manages, and versions prompt templates from YAML files.
"""

import hashlib
from pathlib import Path
from typing import Optional
import yaml
from app.config import get_settings
from app.utils.logger import logger


class PromptTemplate:
    """A single prompt template with variable substitution."""

    def __init__(self, name: str, system_prompt: str, user_template: str,
                 few_shot_examples: list[dict] = None, output_format: str = "",
                 description: str = ""):
        self.name = name
        self.system_prompt = system_prompt
        self.user_template = user_template
        self.few_shot_examples = few_shot_examples or []
        self.output_format = output_format
        self.description = description
        self.version_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute a hash for version tracking."""
        content = f"{self.system_prompt}{self.user_template}{self.output_format}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def format_system(self, **kwargs) -> str:
        """Format the system prompt with variables."""
        try:
            return self.system_prompt.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing variable in system prompt '{self.name}': {e}")
            return self.system_prompt

    def format_user(self, **kwargs) -> str:
        """Format the user template with variables."""
        try:
            return self.user_template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing variable in user template '{self.name}': {e}")
            return self.user_template

    def build_messages(self, **kwargs) -> list[dict[str, str]]:
        """Build a complete message list for LLM API call."""
        messages = [{"role": "system", "content": self.format_system(**kwargs)}]

        # Add few-shot examples
        for example in self.few_shot_examples:
            if "user" in example:
                messages.append({"role": "user", "content": example["user"]})
            if "assistant" in example:
                messages.append({"role": "assistant", "content": example["assistant"]})

        # Add output format instruction if present
        user_content = self.format_user(**kwargs)
        if self.output_format:
            user_content += f"\n\nExpected output format:\n{self.output_format}"

        messages.append({"role": "user", "content": user_content})
        return messages


class PromptManager:
    """Manages all prompt templates loaded from YAML files."""

    def __init__(self):
        self.settings = get_settings()
        self.prompts: dict[str, PromptTemplate] = {}
        self._prompts_dir = Path(self.settings.base_dir) / "prompts"
        self._load_all_prompts()

    def _load_all_prompts(self):
        """Load all YAML prompt files from the prompts directory."""
        if not self._prompts_dir.exists():
            logger.warning(f"Prompts directory not found: {self._prompts_dir}")
            return

        for yaml_file in self._prompts_dir.glob("*.yaml"):
            try:
                self._load_prompt_file(yaml_file)
            except Exception as e:
                logger.error(f"Failed to load prompt file {yaml_file}: {e}")

    def _load_prompt_file(self, filepath: Path):
        """Load a single YAML prompt file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return

        name = data.get("name", filepath.stem)
        template = PromptTemplate(
            name=name,
            system_prompt=data.get("system_prompt", ""),
            user_template=data.get("user_template", ""),
            few_shot_examples=data.get("few_shot_examples", []),
            output_format=data.get("output_format", ""),
            description=data.get("description", ""),
        )

        self.prompts[name] = template
        logger.info(f"Loaded prompt: {name} (v{template.version_hash})")

    def get(self, name: str) -> Optional[PromptTemplate]:
        """Get a prompt template by name."""
        template = self.prompts.get(name)
        if not template:
            logger.warning(f"Prompt template not found: {name}")
        return template

    def get_or_default(self, name: str, default_system: str = "", default_user: str = "") -> PromptTemplate:
        """Get a prompt template or create a default one."""
        template = self.prompts.get(name)
        if template:
            return template
        return PromptTemplate(
            name=name,
            system_prompt=default_system,
            user_template=default_user,
        )

    def reload(self):
        """Reload all prompt templates from disk."""
        self.prompts.clear()
        self._load_all_prompts()
        logger.info(f"Reloaded {len(self.prompts)} prompt templates")

    def list_prompts(self) -> list[dict]:
        """List all loaded prompts with their versions."""
        return [
            {
                "name": t.name,
                "version": t.version_hash,
                "description": t.description,
                "has_examples": len(t.few_shot_examples) > 0,
            }
            for t in self.prompts.values()
        ]


# Singleton
_prompt_manager: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Get or create the singleton prompt manager."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager
