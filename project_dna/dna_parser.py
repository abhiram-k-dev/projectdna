"""
ProjectDNA — DNA Parser
Loads, validates, and slices .dna files for agent context delivery.
"""

from __future__ import annotations
import yaml
from pathlib import Path
from typing import Any, Dict, List, Tuple
from .dna_format import DNAFile, DNA_MANDATORY_PATHS


# Context slices: each agent receives ONLY its relevant DNA section
AGENT_CONTEXT_MAP: Dict[str, List[str]] = {
    "interview_agent":   [],          # empty template — no pre-existing context
    "validator_agent":   ["project"],  # full project for completeness check
    "planner_agent":     ["project.goals", "project.constraints", "project.tech_stack"],
    "builder_agent":     ["project.tech_stack", "project.architecture",
                          "project.tools", "project.rules"],
    "eval_agent":        ["project.goals.success_metrics", "project.rules"],
    "deployment_agent":  ["project.deployment", "project.tools"],
}


class DNAValidationError(Exception):
    """Raised when a .dna file fails validation."""
    def __init__(self, missing: List[str], message: str = ""):
        self.missing = missing
        super().__init__(message or f"Missing mandatory fields: {missing}")


class DNAParser:
    """Parses .dna YAML files into DNAFile models with context slicing."""

    def __init__(self):
        self._dna: DNAFile | None = None

    # ------------------------------------------------------------------ #
    # PUBLIC API                                                           #
    # ------------------------------------------------------------------ #

    def load(self, source: str | Path | dict) -> DNAFile:
        """Load a .dna file from a file path, YAML string, or dict."""
        if isinstance(source, dict):
            raw = source
        elif isinstance(source, Path) or (isinstance(source, str) and "\n" not in source):
            path = Path(source)
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        else:
            raw = yaml.safe_load(source)

        self._dna = DNAFile(**raw)
        return self._dna

    def validate(self) -> Tuple[bool, List[str]]:
        """
        Check all mandatory fields are present and non-empty.
        Returns (is_valid, list_of_missing_field_paths).
        """
        if self._dna is None:
            raise RuntimeError("Call load() before validate()")

        missing: List[str] = []
        for field_path in DNA_MANDATORY_PATHS:
            value = self._get_nested(self._dna.model_dump(), field_path)
            if not value:
                missing.append(field_path)

        return (len(missing) == 0, missing)

    def get_agent_context(self, agent_name: str) -> Dict[str, Any]:
        """
        Return only the DNA sections relevant to the given agent.
        Implements the context-slicing rule: each agent gets its slice only.
        """
        if self._dna is None:
            raise RuntimeError("Call load() before get_agent_context()")

        agent_name = agent_name.lower()
        paths = AGENT_CONTEXT_MAP.get(agent_name)

        if paths is None:
            raise ValueError(f"Unknown agent: {agent_name}. "
                             f"Valid agents: {list(AGENT_CONTEXT_MAP.keys())}")

        if not paths:
            return {"agent": agent_name, "context": {}, "note": "empty template"}

        full = self._dna.model_dump()
        sliced: Dict[str, Any] = {}

        for path in paths:
            value = self._get_nested(full, path)
            self._set_nested(sliced, path, value)

        token_estimate_full = len(str(full))
        token_estimate_slice = len(str(sliced))
        savings_pct = round((1 - token_estimate_slice / max(token_estimate_full, 1)) * 100, 1)

        return {
            "agent": agent_name,
            "context": sliced,
            "token_savings_vs_full": f"{savings_pct}%",
        }

    # ------------------------------------------------------------------ #
    # HELPERS                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _get_nested(data: dict, dotted_path: str) -> Any:
        keys = dotted_path.split(".")
        node = data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
        return node

    @staticmethod
    def _set_nested(target: dict, dotted_path: str, value: Any) -> None:
        keys = dotted_path.split(".")
        node = target
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value
