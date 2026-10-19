"""
Tests for ProjectDNA package.
"""

from pathlib import Path
import pytest
from project_dna import (
    DNAParser,
    GuardrailEngine,
    ProjectDNAPipeline,
)
from project_dna.dna_format import DNAFile


def test_dna_parser_valid_file():
    parser = DNAParser()
    dna = parser.load("samples/todoflow.dna")
    assert isinstance(dna, DNAFile)
    assert dna.project.name == "TodoFlow"

    is_valid, missing = parser.validate()
    assert is_valid is True
    assert len(missing) == 0


def test_dna_parser_invalid_file():
    parser = DNAParser()
    dna = parser.load("samples/invalid_missing_fields.dna")
    assert isinstance(dna, DNAFile)

    is_valid, missing = parser.validate()
    assert is_valid is False
    assert "project.description" in missing
    assert "project.vision" in missing


def test_context_slicing():
    parser = DNAParser()
    parser.load("samples/todoflow.dna")

    planner_ctx = parser.get_agent_context("planner_agent")
    assert "context" in planner_ctx
    assert "token_savings_vs_full" in planner_ctx

    eval_ctx = parser.get_agent_context("eval_agent")
    assert "context" in eval_ctx


def test_guardrails_secret_detection():
    guard = GuardrailEngine()
    clean_code = "def get_items(): return ['task1', 'task2']"
    result_clean = guard.check_secret(clean_code, "main.py")
    assert result_clean.allowed is True

    secret_code = 'OPENAI_API_KEY = "sk-1234567890abcdef123456"'
    result_secret = guard.check_secret(secret_code, "main.py")
    assert result_secret.allowed is False


def test_guardrails_tool_permissions():
    guard = GuardrailEngine(allowed_tools=["file_write", "bash_execute"])
    assert guard.check_permission("file_write").allowed is True
    assert guard.check_permission("forbidden_tool").allowed is False


def test_guardrails_eval_gate():
    guard = GuardrailEngine()
    assert guard.check_eval_gate("eval_passed").allowed is True
    assert guard.check_eval_gate("eval_failed").allowed is False
    assert guard.check_eval_gate(None).allowed is False


def test_pipeline_run_from_dna():
    pipeline = ProjectDNAPipeline()
    result = pipeline.run_from_dna("samples/todoflow.dna")
    assert result.get("pipeline_status") == "complete"
    assert "deployment" in result
    assert result["deployment"]["status"] == "deployed"


def test_export_files(tmp_path):
    pipeline = ProjectDNAPipeline()
    pipeline.run_from_dna("samples/todoflow.dna")
    exported = pipeline.export_files(tmp_path)
    assert len(exported) > 0
    assert any("main.py" in f for f in exported)
    assert any("App.tsx" in f for f in exported)
