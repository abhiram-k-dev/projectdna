"""
ProjectDNA — LangGraph Pipeline Orchestrator
Manages agent handoffs, state, and retry logic using a directed state graph.
"""

from __future__ import annotations
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .dna_format import DNAFile
from .dna_parser import DNAParser
from .agents import (
    A2AMessageBus,
    InterviewAgent, ValidatorAgent, PlannerAgent,
    BuilderAgent, EvalAgent, DeploymentAgent,
)
from .mcp_servers import FilesystemMCP, GitHubMCP, DockerMCP, DatabaseMCP


class ProjectDNAPipeline:
    """
    Orchestrates the full 6-agent pipeline.
    Represents the LangGraph state graph — each agent is a node,
    each A2A message is a directed edge.
    """

    def __init__(self, project_root: str = "/projects", gemini_model=None):
        # Shared infrastructure
        self.db_mcp = DatabaseMCP()
        self.fs_mcp = FilesystemMCP(project_root, guardrail_engine=None)
        self.github_mcp = GitHubMCP()
        self.docker_mcp = DockerMCP()
        self.a2a = A2AMessageBus()
        self.model = gemini_model

        # Build agents
        self.interview_agent   = InterviewAgent(self.fs_mcp, self.db_mcp, self.a2a, gemini_model)
        self.validator_agent   = ValidatorAgent(self.fs_mcp, self.db_mcp, self.a2a, gemini_model)
        self.planner_agent     = PlannerAgent(self.fs_mcp, self.db_mcp, self.a2a, gemini_model)
        self.builder_agent     = BuilderAgent(self.fs_mcp, self.db_mcp, self.github_mcp, self.a2a, gemini_model)
        self.eval_agent        = EvalAgent(self.fs_mcp, self.db_mcp, self.a2a, gemini_model)
        self.deployment_agent  = DeploymentAgent(self.fs_mcp, self.db_mcp, self.docker_mcp, self.a2a, gemini_model)

        self._state: Dict[str, Any] = {}

    def run(self, answers: Dict[str, str], project_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the full pipeline end-to-end.
        answers: dict of interview answers keyed by DNA field path
        Returns: final pipeline result with all stage outputs
        """
        project_id = project_id or uuid.uuid4().hex[:8]
        run_id = uuid.uuid4().hex[:8]

        print(f"\n{'#'*60}")
        print(f"# 🧬 ProjectDNA PIPELINE START")
        print(f"# Project ID : {project_id}")
        print(f"# Run ID     : {run_id}")
        print(f"{'#'*60}")

        self._state = {
            "project_id": project_id,
            "run_id": run_id,
            "stage": "interview",
            "completed_stages": [],
        }

        results: Dict[str, Any] = {}

        # ── NODE 1: Interview Agent ──────────────────────────────────
        self._state["stage"] = "interview"
        dna = self.interview_agent.run_interview(answers, project_id, run_id)
        results["dna"] = dna
        self._state["completed_stages"].append("interview")

        return self._execute_downstream(dna, project_id, run_id, results)

    def run_from_dna(
        self,
        dna_source: Union[DNAFile, str, Path],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute the pipeline starting from an existing .dna file or DNAFile model
        (skips stage 1 interview and proceeds through validation, planning,
        building, evaluation, and deployment).
        """
        if isinstance(dna_source, DNAFile):
            dna = dna_source
        else:
            parser = DNAParser()
            dna = parser.load(dna_source)

        clean_name = dna.project.name.lower().replace(" ", "_") if dna.project.name else uuid.uuid4().hex[:8]
        project_id = project_id or clean_name
        run_id = uuid.uuid4().hex[:8]

        # Register in DB MCP
        self.db_mcp.dna_write("pipeline", project_id, dna.model_dump())

        print(f"\n{'#'*60}")
        print(f"# 🧬 ProjectDNA PIPELINE START (FROM EXISTING DNA)")
        print(f"# Project ID : {project_id}")
        print(f"# Run ID     : {run_id}")
        print(f"{'#'*60}")

        self._state = {
            "project_id": project_id,
            "run_id": run_id,
            "stage": "validation",
            "completed_stages": [],
        }

        results: Dict[str, Any] = {"dna": dna}
        return self._execute_downstream(dna, project_id, run_id, results)

    def _execute_downstream(
        self,
        dna: DNAFile,
        project_id: str,
        run_id: str,
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        # ── NODE 2: Validator Agent ──────────────────────────────────
        self._state["stage"] = "validation"
        validation_report = self.validator_agent.validate(dna, project_id, run_id)
        results["validation"] = validation_report

        if validation_report["validation_status"] == "failed":
            self._state["stage"] = "failed:validation"
            return {**results, "pipeline_status": "failed", "failed_at": "validator_agent",
                    "errors": validation_report["errors"]}

        self._state["completed_stages"].append("validation")

        # ── NODE 3: Planner Agent ────────────────────────────────────
        self._state["stage"] = "planning"
        plan = self.planner_agent.plan(dna, project_id, run_id)
        results["plan"] = plan
        self._state["completed_stages"].append("planning")

        # ── NODE 4: Builder Agent ────────────────────────────────────
        self._state["stage"] = "building"
        build_result = self.builder_agent.build(dna, plan, project_id, run_id)
        results["build"] = build_result
        self._state["completed_stages"].append("building")

        # ── NODE 5: Eval Agent ───────────────────────────────────────
        self._state["stage"] = "evaluation"
        eval_report = self.eval_agent.evaluate(dna, build_result, project_id, run_id)
        results["eval"] = eval_report
        self._state["completed_stages"].append("evaluation")

        if eval_report["eval_status"] == "eval_failed":
            self._state["stage"] = "failed:evaluation"
            return {**results, "pipeline_status": "failed", "failed_at": "eval_agent"}

        # ── NODE 6: Deployment Agent ─────────────────────────────────
        self._state["stage"] = "deployment"
        deploy_result = self.deployment_agent.deploy(dna, project_id, run_id)
        results["deployment"] = deploy_result
        self._state["completed_stages"].append("deployment")

        self._state["stage"] = "complete"

        print(f"\n{'#'*60}")
        print(f"# ✅ PIPELINE COMPLETE")
        print(f"# Stages completed : {', '.join(self._state['completed_stages'])}")
        print(f"# A2A messages     : {len(self.a2a.messages)}")
        print(f"# Generated files  : {len(self.fs_mcp.get_all_files())}")
        if deploy_result.get("url"):
            print(f"# Live URL         : {deploy_result['url']}")
        print(f"{'#'*60}\n")

        return {
            **results,
            "pipeline_status": "complete",
            "project_id": project_id,
            "run_id": run_id,
            "a2a_messages": self.a2a.messages,
            "generated_files": list(self.fs_mcp.get_all_files().keys()),
            "trajectory": self.db_mcp.get_trajectory(run_id),
        }

    def get_state(self) -> Dict[str, Any]:
        return dict(self._state)

    def get_trajectory(self, run_id: str):
        return self.db_mcp.get_trajectory(run_id)

    def export_files(self, target_dir: str | Path) -> List[str]:
        """Export generated in-memory codebase to physical disk directory."""
        return self.fs_mcp.export_to_disk(target_dir)
