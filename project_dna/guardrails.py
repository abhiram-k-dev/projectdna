"""
ProjectDNA — Guardrail Engine
Six deterministic pre-hooks that run BEFORE agent tool calls.
All hooks are blocking — they prevent the action on violation.
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("projectdna.guardrails")


# ------------------------------------------------------------------ #
# RESULT TYPE                                                          #
# ------------------------------------------------------------------ #

@dataclass
class GuardrailResult:
    allowed: bool
    hook_name: str
    message: str
    matched_pattern: Optional[str] = None

    def __str__(self) -> str:
        status = "✅ ALLOWED" if self.allowed else "🚫 BLOCKED"
        return f"[{self.hook_name}] {status} — {self.message}"


# ------------------------------------------------------------------ #
# SECRET PATTERNS (Guardrail 1)                                        #
# ------------------------------------------------------------------ #

SECRET_PATTERNS = [
    (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}',
     "API key assignment"),
    (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'][^"\']{6,}["\']',
     "Password literal"),
    (r'(?i)(secret[_-]?key|secret)\s*[=:]\s*["\']?[A-Za-z0-9_\-]{16,}',
     "Secret key assignment"),
    (r'(?i)(token|bearer)\s*[=:]\s*["\']?[A-Za-z0-9_\-\.]{20,}',
     "Token literal"),
    (r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----',
     "PEM private key"),
    (r'(?i)(database_url|db_url|postgres_url|redis_url)\s*[=:]\s*["\']?[a-z]+://',
     "Database connection string"),
    (r'AIza[0-9A-Za-z_\-]{35}',
     "Google API key"),
    (r'sk-[A-Za-z0-9]{10,}',
     "OpenAI-style secret key"),
]


# ------------------------------------------------------------------ #
# GUARDRAIL ENGINE                                                     #
# ------------------------------------------------------------------ #

class GuardrailEngine:
    """
    Implements all 6 ProjectDNA security pre-hooks.
    Every method returns a GuardrailResult — callers must check .allowed.
    """

    def __init__(
        self,
        allowed_tools: List[str] | None = None,
        output_requirements: List[str] | None = None,
        agent_identity: str = "unknown_agent",
    ):
        self.allowed_tools: List[str] = allowed_tools or []
        self.output_requirements: List[str] = output_requirements or []
        self.agent_identity: str = agent_identity
        self._retry_counters: Dict[str, int] = {}
        self._dna_writers = {"interview_agent", "validator_agent"}
        self._violations: List[str] = []

    # ---------------------------------------------------------------- #
    # GUARDRAIL 1 — SECRET DETECTION HOOK                               #
    # ---------------------------------------------------------------- #

    def check_secret(self, file_content: str, file_path: str = "") -> GuardrailResult:
        """
        Scan file content for hardcoded secrets before any file_write().
        Blocks the write if a secret pattern is detected.
        """
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, file_content):
                msg = (f"Hardcoded secret detected in '{file_path}': "
                       f"pattern type '{label}'. Write blocked.")
                self._log_violation("SECRET_DETECTION_HOOK", msg)
                return GuardrailResult(
                    allowed=False,
                    hook_name="SECRET_DETECTION_HOOK",
                    message=msg,
                    matched_pattern=label,
                )
        return GuardrailResult(
            allowed=True,
            hook_name="SECRET_DETECTION_HOOK",
            message=f"No secrets detected in '{file_path}'. Write allowed.",
        )

    # ---------------------------------------------------------------- #
    # GUARDRAIL 2 — TOOL PERMISSION HOOK                                #
    # ---------------------------------------------------------------- #

    def check_permission(self, tool_name: str) -> GuardrailResult:
        """
        Verify tool_name is in the DNA allowed_tools list.
        Blocks the call if the tool is not whitelisted.
        """
        if tool_name in self.allowed_tools:
            return GuardrailResult(
                allowed=True,
                hook_name="TOOL_PERMISSION_HOOK",
                message=f"Tool '{tool_name}' is in allowed_tools. Call permitted.",
            )
        msg = (f"Tool '{tool_name}' is NOT in allowed_tools {self.allowed_tools}. "
               f"Call blocked for agent '{self.agent_identity}'.")
        self._log_violation("TOOL_PERMISSION_HOOK", msg)
        return GuardrailResult(
            allowed=False,
            hook_name="TOOL_PERMISSION_HOOK",
            message=msg,
        )

    # ---------------------------------------------------------------- #
    # GUARDRAIL 3 — SCOPE ENFORCEMENT HOOK                              #
    # ---------------------------------------------------------------- #

    def check_scope(self, feature_description: str) -> GuardrailResult:
        """
        Verify a proposed feature exists in DNA output_requirements.must_include.
        Uses keyword overlap for semantic matching.
        """
        if not self.output_requirements:
            return GuardrailResult(
                allowed=False,
                hook_name="SCOPE_ENFORCEMENT_HOOK",
                message="output_requirements is empty — cannot verify scope. Blocked.",
            )

        feature_words = set(feature_description.lower().split())
        for req in self.output_requirements:
            req_words = set(req.lower().split())
            if feature_words & req_words:
                return GuardrailResult(
                    allowed=True,
                    hook_name="SCOPE_ENFORCEMENT_HOOK",
                    message=f"Feature '{feature_description}' matches requirement '{req}'. Allowed.",
                )

        msg = (f"Feature '{feature_description}' is NOT in output_requirements "
               f"{self.output_requirements}. Implementation blocked.")
        self._log_violation("SCOPE_ENFORCEMENT_HOOK", msg)
        return GuardrailResult(
            allowed=False,
            hook_name="SCOPE_ENFORCEMENT_HOOK",
            message=msg,
        )

    # ---------------------------------------------------------------- #
    # GUARDRAIL 4 — EVAL GATE HOOK                                      #
    # ---------------------------------------------------------------- #

    def check_eval_gate(self, eval_status: str) -> GuardrailResult:
        """
        Block deployment unless Eval Agent has returned 'eval_passed'.
        """
        if eval_status == "eval_passed":
            return GuardrailResult(
                allowed=True,
                hook_name="EVAL_GATE_HOOK",
                message="Eval status is 'eval_passed'. Deployment allowed.",
            )
        msg = (f"Eval status is '{eval_status}' — must be 'eval_passed' before deployment. "
               f"Deployment blocked. Run Eval Agent first.")
        self._log_violation("EVAL_GATE_HOOK", msg)
        return GuardrailResult(
            allowed=False,
            hook_name="EVAL_GATE_HOOK",
            message=msg,
        )

    # ---------------------------------------------------------------- #
    # GUARDRAIL 5 — RETRY LIMIT HOOK                                    #
    # ---------------------------------------------------------------- #

    def check_retry_limit(self, stage_id: str, max_retries: int = 3) -> GuardrailResult:
        """
        Block further automated retries after max_retries consecutive failures.
        Increments the retry counter for the stage on each call.
        """
        self._retry_counters[stage_id] = self._retry_counters.get(stage_id, 0) + 1
        count = self._retry_counters[stage_id]

        if count <= max_retries:
            return GuardrailResult(
                allowed=True,
                hook_name="RETRY_LIMIT_HOOK",
                message=f"Stage '{stage_id}' retry {count}/{max_retries}. Retry allowed.",
            )

        msg = (f"Stage '{stage_id}' has failed {count} times (max {max_retries}). "
               f"Automated retries blocked. Human review required.")
        self._log_violation("RETRY_LIMIT_HOOK", msg)
        return GuardrailResult(
            allowed=False,
            hook_name="RETRY_LIMIT_HOOK",
            message=msg,
        )

    def get_retry_count(self, stage_id: str) -> int:
        return self._retry_counters.get(stage_id, 0)

    # ---------------------------------------------------------------- #
    # GUARDRAIL 6 — DNA MUTATION GUARD                                  #
    # ---------------------------------------------------------------- #

    def check_dna_mutation(self, requesting_agent: str) -> GuardrailResult:
        """
        Block DNA file writes from any agent other than interview_agent
        or validator_agent.
        """
        agent = requesting_agent.lower()
        if agent in self._dna_writers:
            return GuardrailResult(
                allowed=True,
                hook_name="DNA_MUTATION_GUARD",
                message=f"Agent '{agent}' is authorized to write DNA files.",
            )
        msg = (f"Agent '{agent}' is NOT authorized to modify DNA files. "
               f"Only interview_agent and validator_agent may write DNA. Write blocked.")
        self._log_violation("DNA_MUTATION_GUARD", msg)
        return GuardrailResult(
            allowed=False,
            hook_name="DNA_MUTATION_GUARD",
            message=msg,
        )

    # ---------------------------------------------------------------- #
    # INTERNAL                                                           #
    # ---------------------------------------------------------------- #

    def _log_violation(self, hook: str, msg: str) -> None:
        logger.warning("[GUARDRAIL VIOLATION] %s: %s", hook, msg)
        self._violations.append(f"[{hook}] {msg}")

    @property
    def violations(self) -> List[str]:
        return list(self._violations)
