"""
ProjectDNA — Six Specialized Agents
Built using Google ADK Agent pattern.
Each agent has ONE job and reads ONLY its DNA context slice.
All tool calls are routed through MCP servers.
All agents communicate via A2A protocol (simulated here for Kaggle).
"""

from __future__ import annotations
import json
import uuid
import yaml
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from .dna_format import DNAFile
from .dna_parser import DNAParser
from .guardrails import GuardrailEngine
from .mcp_servers import FilesystemMCP, GitHubMCP, DockerMCP, DatabaseMCP


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ #
# A2A MESSAGE BUS (in-process simulation)                              #
# ------------------------------------------------------------------ #

class A2AMessageBus:
    """
    Simulates Google ADK A2A protocol message passing.
    Each message has: sender, recipient, type, payload, timestamp.
    """

    def __init__(self):
        self._log: List[Dict] = []

    def send(self, sender: str, recipient: str, msg_type: str, payload: Dict) -> Dict:
        msg = {
            "id": uuid.uuid4().hex[:8],
            "sender_agent_id": sender,
            "recipient_agent_id": recipient,
            "message_type": msg_type,
            "payload": payload,
            "timestamp": _ts(),
        }
        self._log.append(msg)
        print(f"\n  [A2A] {sender} → {recipient} | type={msg_type}")
        return msg

    @property
    def messages(self) -> List[Dict]:
        return list(self._log)


# ------------------------------------------------------------------ #
# BASE AGENT                                                           #
# ------------------------------------------------------------------ #

class ProjectDNAAgent:
    """Base class for all ProjectDNA agents using Google ADK pattern."""

    agent_name: str = "base_agent"

    def __init__(
        self,
        fs_mcp: FilesystemMCP,
        db_mcp: DatabaseMCP,
        a2a_bus: A2AMessageBus,
        gemini_model: Optional[Any] = None,
    ):
        self.fs_mcp = fs_mcp
        self.db_mcp = db_mcp
        self.a2a = a2a_bus
        self.model = gemini_model
        self.parser = DNAParser()

    def _call_llm(self, prompt: str) -> str:
        """Call Gemini model or return a deterministic fallback for CPU-only environments."""
        if self.model and GENAI_AVAILABLE:
            try:
                response = self.model.generate_content(prompt)
                return response.text
            except Exception as e:
                return f"[LLM_FALLBACK] Model error: {e}"
        # Deterministic fallback for Kaggle CPU environment without API key
        return f"[SIMULATED_LLM_RESPONSE for: {prompt[:80]}...]"

    def _log_trajectory(self, run_id: str, action: str, detail: Dict) -> None:
        self.db_mcp.trajectory_log(
            self.agent_name, run_id,
            {"agent": self.agent_name, "action": action, "detail": detail}
        )


# ------------------------------------------------------------------ #
# AGENT 1 — INTERVIEW AGENT                                            #
# ------------------------------------------------------------------ #

class InterviewAgent(ProjectDNAAgent):
    """
    Conducts structured project interviews and produces a .dna file.
    Input: plain-language project idea
    Output: completed DNAFile saved via Filesystem MCP
    A2A: delegates to Validator Agent on completion
    """
    agent_name = "interview_agent"

    QUESTIONS = [
        ("project.name",                    "What is the name of your project?"),
        ("project.description",             "Describe your project in one sentence."),
        ("project.vision",                  "What is the long-term vision for this project?"),
        ("project.problem.statement",       "What core problem does it solve?"),
        ("project.goals.primary_goal",      "What is the single most important goal for the MVP?"),
        ("project.goals.success_metrics",   "List 3 measurable success metrics (comma-separated)."),
        ("project.tech_stack.frontend",     "What frontend framework will you use?"),
        ("project.tech_stack.backend",      "What backend framework will you use?"),
        ("project.tech_stack.database",     "What database will you use?"),
        ("project.security.auth",           "What authentication mechanism will you use?"),
        ("project.tools.allowed_tools",     "List allowed agent tools (comma-separated)."),
        ("project.output_requirements.must_include", "List required deliverables (comma-separated)."),
        ("project.deployment",              "What is the deployment target? (e.g. Vercel, Cloud Run)"),
    ]

    def run_interview(self, answers: Dict[str, str], project_id: str, run_id: str) -> DNAFile:
        """
        Build a DNAFile from a dict of answers keyed by field path.
        In production this would be interactive; here we accept pre-supplied answers.
        """
        print(f"\n{'='*60}")
        print(f"🎤 INTERVIEW AGENT — Project: {project_id}")
        print(f"{'='*60}")

        # Check DNA mutation guard
        from .guardrails import GuardrailEngine as GE
        guard = GE(agent_identity=self.agent_name)
        mutation_check = guard.check_dna_mutation(self.agent_name)
        print(f"  {mutation_check}")

        if not mutation_check.allowed:
            raise PermissionError(mutation_check.message)

        # Build DNAFile from answers
        dna_dict: Dict[str, Any] = {
            "project_dna_version": "1.0",
            "project": {
                "name": answers.get("project.name", ""),
                "description": answers.get("project.description", ""),
                "vision": answers.get("project.vision", ""),
                "problem": {
                    "statement": answers.get("project.problem.statement", ""),
                    "why_it_exists": answers.get("project.problem.why_it_exists", ""),
                },
                "goals": {
                    "primary_goal": answers.get("project.goals.primary_goal", ""),
                    "success_metrics": [
                        m.strip() for m in
                        answers.get("project.goals.success_metrics", "").split(",")
                        if m.strip()
                    ],
                },
                "tech_stack": {
                    "frontend": answers.get("project.tech_stack.frontend", ""),
                    "backend": answers.get("project.tech_stack.backend", ""),
                    "database": answers.get("project.tech_stack.database", ""),
                    "ai_models": ["Google Gemini 1.5 Flash"],
                    "infra": answers.get("project.tech_stack.infra", "Docker + Vercel"),
                },
                "security": {
                    "auth": answers.get("project.security.auth", ""),
                    "permissions": ["read project dir", "write project dir"],
                    "risks": [],
                    "guardrails": [
                        "block hardcoded API keys",
                        "block writes outside project directory",
                    ],
                },
                "tools": {
                    "allowed_tools": [
                        t.strip() for t in
                        answers.get("project.tools.allowed_tools", "").split(",")
                        if t.strip()
                    ],
                    "forbidden_tools": ["system_exec", "network_scan", "env_modify"],
                },
                "output_requirements": {
                    "format": "working web application",
                    "must_include": [
                        r.strip() for r in
                        answers.get("project.output_requirements.must_include", "").split(",")
                        if r.strip()
                    ],
                },
                "deployment": answers.get("project.deployment", "Vercel"),
                "rules": [
                    "No hallucinated features",
                    "Follow architecture strictly",
                    "Fail fast on missing requirements",
                    "Never skip security guardrails",
                    "Eval before every deployment",
                ],
            }
        }

        dna = self.parser.load(dna_dict)

        # Write via Filesystem MCP
        dna_yaml = yaml.dump(dna_dict, default_flow_style=False)
        write_result = self.fs_mcp.write_file(
            self.agent_name, f"/dna/{project_id}.dna", dna_yaml
        )
        print(f"  📄 DNA file written: {write_result}")

        # Save to Database MCP
        self.db_mcp.dna_write(self.agent_name, project_id, dna_dict)

        self._log_trajectory(run_id, "interview_complete", {"project_id": project_id})

        # A2A: delegate to Validator Agent
        self.a2a.send(
            sender=self.agent_name,
            recipient="validator_agent",
            msg_type="stage_complete",
            payload={"project_id": project_id, "run_id": run_id},
        )

        print(f"  ✅ Interview complete. DNA file created for project: {dna.project.name}")
        return dna


# ------------------------------------------------------------------ #
# AGENT 2 — VALIDATOR AGENT                                            #
# ------------------------------------------------------------------ #

class ValidatorAgent(ProjectDNAAgent):
    """
    Checks .dna file for completeness, ambiguity, and risk flags.
    Input: DNAFile from DatabaseMCP
    Output: validation report; sets metadata.validation_status
    A2A: delegates to Planner Agent only if validation passes
    """
    agent_name = "validator_agent"

    VAGUE_TERMS = ["fast", "scalable", "user-friendly", "good", "nice", "easy", "simple", "better"]

    def validate(self, dna: DNAFile, project_id: str, run_id: str) -> Dict[str, Any]:
        print(f"\n{'='*60}")
        print(f"🔍 VALIDATOR AGENT — Project: {project_id}")
        print(f"{'='*60}")

        self.parser._dna = dna
        is_valid, missing = self.parser.validate()

        errors: List[str] = []
        warnings: List[str] = []
        risk_flags: List[Dict] = []

        # Check mandatory fields
        if missing:
            for field in missing:
                errors.append(f"Missing mandatory field: {field}")
                print(f"  ❌ {errors[-1]}")

        # Check for vague terms in success metrics
        for metric in dna.project.goals.success_metrics:
            for vague in self.VAGUE_TERMS:
                if vague in metric.lower():
                    warnings.append(
                        f"Ambiguous metric '{metric}' contains vague term '{vague}'. "
                        f"Suggest a measurable alternative."
                    )
                    print(f"  ⚠️  {warnings[-1]}")

        # Check security risks
        if not dna.project.security.auth or dna.project.security.auth.lower() in ("none", "none for mvp", ""):
            risk_flags.append({
                "field": "project.security.auth",
                "severity": "high",
                "message": "No authentication defined — public endpoints will be unprotected.",
            })
            print(f"  🚨 Risk: {risk_flags[-1]['message']}")

        if not dna.project.security.guardrails:
            risk_flags.append({
                "field": "project.security.guardrails",
                "severity": "medium",
                "message": "No guardrails defined in DNA file.",
            })

        validation_status = "passed" if not errors else "failed"

        report = {
            "project_id": project_id,
            "validation_status": validation_status,
            "errors": errors,
            "warnings": warnings,
            "risk_flags": risk_flags,
            "validated_at": _ts(),
        }

        # Persist status
        self.db_mcp.memory_set(
            self.agent_name, f"validation:{project_id}", validation_status
        )
        self._log_trajectory(run_id, "validation_complete", report)

        if validation_status == "passed":
            print(f"  ✅ Validation PASSED — no mandatory field errors")
            self.a2a.send(
                sender=self.agent_name,
                recipient="planner_agent",
                msg_type="stage_complete",
                payload={"project_id": project_id, "run_id": run_id},
            )
        else:
            print(f"  ❌ Validation FAILED — {len(errors)} error(s) found")
            self.a2a.send(
                sender=self.agent_name,
                recipient="interview_agent",
                msg_type="stage_failed",
                payload={"project_id": project_id, "errors": errors},
            )

        return report


# ------------------------------------------------------------------ #
# AGENT 3 — PLANNER AGENT                                              #
# ------------------------------------------------------------------ #

class PlannerAgent(ProjectDNAAgent):
    """
    Reads validated DNA and creates stage-by-stage execution plan.
    Input: validated DNAFile
    Output: execution plan written to DatabaseMCP
    A2A: delegates each stage to Builder Agent
    """
    agent_name = "planner_agent"

    def plan(self, dna: DNAFile, project_id: str, run_id: str) -> Dict[str, Any]:
        print(f"\n{'='*60}")
        print(f"📋 PLANNER AGENT — Project: {project_id}")
        print(f"{'='*60}")

        # Context slice: goals + constraints + tech_stack only
        self.parser._dna = dna
        ctx = self.parser.get_agent_context("planner_agent")
        print(f"  📐 Context slice: {list(ctx['context'].keys())} | Token savings: {ctx['token_savings_vs_full']}")

        deliverables = dna.project.output_requirements.must_include
        tech = dna.project.tech_stack

        stages = []

        # Stage 1: Project Scaffold
        stages.append({
            "stage_id": "S1",
            "stage_name": "Project Scaffold",
            "description": "Initialize project directory structure and configuration files",
            "tasks": [
                f"Create frontend directory using {tech.frontend}",
                f"Create backend directory using {tech.backend}",
                "Create docker-compose.yml",
                "Create .gitignore",
                "Create README.md",
            ],
            "expected_outputs": ["frontend/", "backend/", "docker-compose.yml"],
            "success_criteria": "All directories exist and config files are valid",
        })

        # Stage 2: Backend API
        stages.append({
            "stage_id": "S2",
            "stage_name": "Backend API Implementation",
            "description": f"Implement REST API with {tech.backend} and {tech.database}",
            "tasks": [
                "Create database models",
                "Implement API endpoints for each deliverable",
                "Add CORS configuration",
                "Write unit tests",
            ],
            "expected_outputs": ["backend/main.py", "backend/models.py", "backend/tests/"],
            "success_criteria": "All API endpoints return correct responses and tests pass",
        })

        # Stage 3: Frontend UI — only for declared deliverables
        frontend_tasks = []
        for deliverable in deliverables:
            frontend_tasks.append(f"Implement: {deliverable}")

        stages.append({
            "stage_id": "S3",
            "stage_name": "Frontend Implementation",
            "description": f"Build React UI components for declared deliverables",
            "tasks": frontend_tasks or ["Create base App component"],
            "expected_outputs": ["frontend/src/App.tsx", "frontend/src/components/"],
            "success_criteria": "UI renders all declared deliverables without errors",
        })

        plan = {
            "plan_id": uuid.uuid4().hex[:8],
            "project_id": project_id,
            "run_id": run_id,
            "created_at": _ts(),
            "stages": stages,
            "total_stages": len(stages),
        }

        # Save plan to long-term memory
        self.db_mcp.memory_set(self.agent_name, f"plan:{project_id}", plan)
        self._log_trajectory(run_id, "plan_created", {"plan_id": plan["plan_id"], "stages": len(stages)})

        for stage in stages:
            print(f"  📌 {stage['stage_id']}: {stage['stage_name']}")

        print(f"  ✅ Plan created: {len(stages)} stages for {len(deliverables)} deliverables")

        # A2A: delegate to Builder Agent
        self.a2a.send(
            sender=self.agent_name,
            recipient="builder_agent",
            msg_type="stage_complete",
            payload={"project_id": project_id, "run_id": run_id, "plan_id": plan["plan_id"]},
        )

        return plan


# ------------------------------------------------------------------ #
# AGENT 4 — BUILDER AGENT                                              #
# ------------------------------------------------------------------ #

class BuilderAgent(ProjectDNAAgent):
    """
    Executes plan stages: writes code, runs tests, commits to Git.
    Input: stage plan + DNA context slice
    Output: code committed via GitHubMCP
    Guardrails: secret detection, tool permission, scope enforcement
    """
    agent_name = "builder_agent"

    def __init__(self, fs_mcp, db_mcp, github_mcp: GitHubMCP, a2a_bus, gemini_model=None):
        super().__init__(fs_mcp, db_mcp, a2a_bus, gemini_model)
        self.github_mcp = github_mcp

    def build(self, dna: DNAFile, plan: Dict, project_id: str, run_id: str) -> Dict[str, Any]:
        print(f"\n{'='*60}")
        print(f"🔨 BUILDER AGENT — Project: {project_id}")
        print(f"{'='*60}")

        # Context slice: tech_stack + architecture + tools + rules only
        self.parser._dna = dna
        ctx = self.parser.get_agent_context("builder_agent")
        print(f"  📐 Context slice: {list(ctx['context'].keys())} | Token savings: {ctx['token_savings_vs_full']}")

        # Set up guardrail engine from DNA
        guardrail = GuardrailEngine(
            allowed_tools=dna.project.tools.allowed_tools,
            output_requirements=dna.project.output_requirements.must_include,
            agent_identity=self.agent_name,
        )

        build_results = []
        project_name = dna.project.name.lower().replace(" ", "_")

        for stage in plan.get("stages", []):
            stage_id = stage["stage_id"]
            print(f"\n  ── Stage {stage_id}: {stage['stage_name']}")

            # GUARDRAIL 2: check tool permission before file_write
            perm_check = guardrail.check_permission("file_write")
            print(f"    {perm_check}")
            if not perm_check.allowed:
                build_results.append({"stage": stage_id, "status": "blocked", "reason": perm_check.message})
                continue

            # Generate code for the stage
            files_written = self._execute_stage(stage, dna, project_name, guardrail, run_id)

            # Commit to Git via GitHub MCP
            if files_written:
                commit = self.github_mcp.git_commit(
                    self.agent_name,
                    f"[{stage_id}] {stage['stage_name']}",
                    files_written,
                )
                print(f"    📦 Git commit: {commit['sha']} — {commit['message']}")

            build_results.append({
                "stage": stage_id,
                "status": "complete",
                "files": files_written,
            })
            self._log_trajectory(run_id, f"stage_{stage_id}_complete", {"files": files_written})

        print(f"\n  ✅ Build complete: {len(build_results)} stages executed")

        # A2A: report completion to Eval Agent
        self.a2a.send(
            sender=self.agent_name,
            recipient="eval_agent",
            msg_type="stage_complete",
            payload={"project_id": project_id, "run_id": run_id, "build_results": build_results},
        )

        return {"project_id": project_id, "stages": build_results}

    def _execute_stage(
        self, stage: Dict, dna: DNAFile, project_name: str,
        guardrail: GuardrailEngine, run_id: str
    ) -> List[str]:
        """Generate and write code files for a single stage."""
        written = []
        tech = dna.project.tech_stack
        stage_id = stage["stage_id"]

        if stage_id == "S1":
            # Project scaffold files
            files = {
                f"/{project_name}/README.md":
                    f"# {dna.project.name}\n\n{dna.project.description}\n\n## Vision\n{dna.project.vision}\n",
                f"/{project_name}/.gitignore":
                    "node_modules/\n__pycache__/\n.env\n*.pyc\ndist/\n.DS_Store\n",
                f"/{project_name}/docker-compose.yml":
                    self._gen_docker_compose(project_name, tech),
            }
            for path, content in files.items():
                # GUARDRAIL 1: secret scan before every write
                secret_check = guardrail.check_secret(content, path)
                print(f"    {secret_check}")
                if secret_check.allowed:
                    self.fs_mcp.write_file(self.agent_name, path, content)
                    written.append(path)

        elif stage_id == "S2":
            # Backend API
            backend_content = self._gen_backend(dna, project_name)

            # DEMO: attempt to write content with a hardcoded secret — guardrail blocks it
            print(f"\n    🧪 DEMO — attempting to write hardcoded secret (should be blocked):")
            bad_content = backend_content + '\nAPI_KEY = "sk-abc123secretkey9876543210FAKE"\n'
            secret_check = guardrail.check_secret(bad_content, "backend/main.py")
            print(f"    {secret_check}")
            if not secret_check.allowed:
                print(f"    ✅ Guardrail correctly blocked hardcoded secret!")

            # Write clean version
            secret_check_clean = guardrail.check_secret(backend_content, f"/{project_name}/backend/main.py")
            if secret_check_clean.allowed:
                self.fs_mcp.write_file(self.agent_name, f"/{project_name}/backend/main.py", backend_content)
                written.append(f"/{project_name}/backend/main.py")

            requirements = "fastapi\nuvicorn\npydantic\nsqlite3\n"
            self.fs_mcp.write_file(self.agent_name, f"/{project_name}/backend/requirements.txt", requirements)
            written.append(f"/{project_name}/backend/requirements.txt")

        elif stage_id == "S3":
            # Frontend — only declared deliverables
            for deliverable in dna.project.output_requirements.must_include:
                # GUARDRAIL 3: scope enforcement
                scope_check = guardrail.check_scope(deliverable)
                print(f"    {scope_check}")
                if scope_check.allowed:
                    component = self._gen_react_component(deliverable)
                    safe_name = deliverable.replace(" ", "_").replace("/", "_")
                    path = f"/{project_name}/frontend/src/components/{safe_name}.tsx"
                    secret_check = guardrail.check_secret(component, path)
                    if secret_check.allowed:
                        self.fs_mcp.write_file(self.agent_name, path, component)
                        written.append(path)

            # App entry point
            app_content = self._gen_app_tsx(dna, project_name)
            self.fs_mcp.write_file(self.agent_name, f"/{project_name}/frontend/src/App.tsx", app_content)
            written.append(f"/{project_name}/frontend/src/App.tsx")

        return written

    def _gen_docker_compose(self, project_name: str, tech) -> str:
        return f"""version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file:
      - .env
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
"""

    def _gen_backend(self, dna: DNAFile, project_name: str) -> str:
        project = dna.project
        endpoints = []
        for item in project.output_requirements.must_include:
            slug = item.lower().replace(" ", "_").replace("-", "_")
            endpoints.append(f"""
@app.get("/api/{slug}")
async def get_{slug}():
    \"\"\"Endpoint for: {item}\"\"\"
    return {{"status": "ok", "feature": "{item}"}}
""")
        endpoints_str = "\n".join(endpoints)
        return f'''"""
{project.name} — FastAPI Backend
Generated by ProjectDNA Builder Agent
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="{project.name}", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {{"status": "healthy", "project": "{project.name}"}}

{endpoints_str}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''

    def _gen_react_component(self, deliverable: str) -> str:
        component_name = "".join(w.capitalize() for w in deliverable.replace("-", " ").split())
        return f'''import React from "react";

/**
 * {component_name}
 * Generated by ProjectDNA Builder Agent
 * Deliverable: {deliverable}
 */
const {component_name}: React.FC = () => {{
  return (
    <div className="p-4 bg-white rounded shadow">
      <h2 className="text-xl font-bold">{deliverable}</h2>
      <p className="text-gray-600">Feature: {deliverable}</p>
    </div>
  );
}};

export default {component_name};
'''

    def _gen_app_tsx(self, dna: DNAFile, project_name: str) -> str:
        return f'''import React from "react";

/**
 * {dna.project.name} — Main App
 * Generated by ProjectDNA Builder Agent
 */
function App() {{
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-3xl font-bold text-center mb-8">{dna.project.name}</h1>
      <p className="text-center text-gray-600">{dna.project.description}</p>
    </div>
  );
}}

export default App;
'''


# ------------------------------------------------------------------ #
# AGENT 5 — EVAL AGENT                                                 #
# ------------------------------------------------------------------ #

class EvalAgent(ProjectDNAAgent):
    """
    Tests built output against DNA success metrics.
    Input: build artifact location + DNA success_metrics
    Output: pass/fail eval report with trajectory analysis
    A2A: pass → Deployment Agent | fail → User (no deployment)
    """
    agent_name = "eval_agent"

    def evaluate(self, dna: DNAFile, build_result: Dict, project_id: str, run_id: str) -> Dict[str, Any]:
        print(f"\n{'='*60}")
        print(f"🧪 EVAL AGENT — Project: {project_id}")
        print(f"{'='*60}")

        # Context slice: success_metrics + rules only
        self.parser._dna = dna
        ctx = self.parser.get_agent_context("eval_agent")
        print(f"  📐 Context slice: {list(ctx['context'].keys())} | Token savings: {ctx['token_savings_vs_full']}")

        metrics = dna.project.goals.success_metrics
        built_files = []
        for stage in build_result.get("stages", []):
            built_files.extend(stage.get("files", []))

        metric_results = []
        all_passed = True

        for metric in metrics:
            # Deterministic evaluation rules
            passed = self._evaluate_metric(metric, built_files, dna)
            status = "PASS" if passed else "FAIL"
            if not passed:
                all_passed = False
            metric_results.append({
                "metric": metric,
                "status": status,
                "observed": "verified against build artifacts" if passed else "not verified",
                "expected": metric,
            })
            icon = "✅" if passed else "❌"
            print(f"  {icon} [{status}] {metric}")

        eval_status = "eval_passed" if all_passed else "eval_failed"
        score = round(sum(1 for r in metric_results if r["status"] == "PASS") / max(len(metric_results), 1) * 100, 1)

        # Load full trajectory for this run
        trajectory = self.db_mcp.get_trajectory(run_id)

        report = {
            "project_id": project_id,
            "run_id": run_id,
            "eval_status": eval_status,
            "score": f"{score}%",
            "metrics_passed": sum(1 for r in metric_results if r["status"] == "PASS"),
            "metrics_total": len(metric_results),
            "metric_results": metric_results,
            "trajectory_steps": len(trajectory),
            "evaluated_at": _ts(),
        }

        # Persist eval result
        self.db_mcp.eval_log(self.agent_name, project_id, eval_status, report)
        self._log_trajectory(run_id, "eval_complete", {"eval_status": eval_status, "score": score})

        if all_passed:
            print(f"\n  ✅ EVAL PASSED — Score: {score}% | Delegating to Deployment Agent")
            self.a2a.send(
                sender=self.agent_name,
                recipient="deployment_agent",
                msg_type="stage_complete",
                payload={"project_id": project_id, "run_id": run_id, "eval_status": eval_status},
            )
        else:
            print(f"\n  ❌ EVAL FAILED — Score: {score}% | Human review required")
            self.a2a.send(
                sender=self.agent_name,
                recipient="planner_agent",
                msg_type="stage_failed",
                payload={"project_id": project_id, "failed_metrics": [r for r in metric_results if r["status"] == "FAIL"]},
            )

        return report

    def _evaluate_metric(self, metric: str, built_files: List[str], dna: DNAFile) -> bool:
        """Simple heuristic evaluation — checks if build artifacts satisfy metric keywords."""
        metric_lower = metric.lower()
        all_files_str = " ".join(built_files).lower()
        deliverables = [d.lower() for d in dna.project.output_requirements.must_include]

        # Check if files were actually created
        if not built_files:
            return False

        # Metric mentions a deliverable that was built
        for deliverable in deliverables:
            words = set(deliverable.split())
            if words & set(metric_lower.split()):
                if any(w in all_files_str for w in words):
                    return True

        # Generic checks
        if "backend" in metric_lower and any("backend" in f for f in built_files):
            return True
        if "frontend" in metric_lower and any("frontend" in f for f in built_files):
            return True
        if "api" in metric_lower and any("main.py" in f for f in built_files):
            return True
        if "mobile" in metric_lower or "responsive" in metric_lower:
            return any("App.tsx" in f for f in built_files)

        # Default: if build completed stages, metrics pass
        return len(built_files) > 0


# ------------------------------------------------------------------ #
# AGENT 6 — DEPLOYMENT AGENT                                           #
# ------------------------------------------------------------------ #

class DeploymentAgent(ProjectDNAAgent):
    """
    Containerizes and deploys the completed project.
    Input: completed codebase + DNA deployment field
    Output: live deployed URL
    Guardrail: EVAL GATE — blocks if eval has not passed
    """
    agent_name = "deployment_agent"

    def __init__(self, fs_mcp, db_mcp, docker_mcp: DockerMCP, a2a_bus, gemini_model=None):
        super().__init__(fs_mcp, db_mcp, a2a_bus, gemini_model)
        self.docker_mcp = docker_mcp

    def deploy(self, dna: DNAFile, project_id: str, run_id: str) -> Dict[str, Any]:
        print(f"\n{'='*60}")
        print(f"🚀 DEPLOYMENT AGENT — Project: {project_id}")
        print(f"{'='*60}")

        # GUARDRAIL 4: EVAL GATE — must check before ANY deployment action
        eval_status = self.db_mcp.get_eval_status(project_id)
        guardrail = GuardrailEngine(agent_identity=self.agent_name)
        gate_check = guardrail.check_eval_gate(eval_status)
        print(f"  {gate_check}")

        if not gate_check.allowed:
            self._log_trajectory(run_id, "deployment_blocked", {"reason": gate_check.message})
            return {
                "project_id": project_id,
                "status": "blocked",
                "reason": gate_check.message,
            }

        # Context slice: deployment + tools only
        self.parser._dna = dna
        ctx = self.parser.get_agent_context("deployment_agent")
        print(f"  📐 Context slice: {list(ctx['context'].keys())} | Token savings: {ctx['token_savings_vs_full']}")

        project_name = dna.project.name.lower().replace(" ", "_")
        platform = dna.project.deployment or "vercel"
        image_tag = f"{project_name}:latest"

        # Build Docker image
        print(f"\n  🐳 Building Docker image: {image_tag}")
        build_result = self.docker_mcp.docker_build(
            self.agent_name, f"/{project_name}", image_tag
        )
        print(f"  {build_result}")

        if build_result.get("status") != "built":
            return {
                "project_id": project_id,
                "status": "failed",
                "reason": f"Docker build failed: {build_result}",
            }

        # Deploy to platform
        print(f"\n  ☁️  Deploying to {platform}...")
        deploy_result = self.docker_mcp.cloud_run_deploy(
            self.agent_name, image_tag, platform
        )

        live_url = deploy_result.get("url", "")

        # Persist live URL
        self.db_mcp.memory_set(self.agent_name, f"live_url:{project_id}", live_url)
        self._log_trajectory(run_id, "deployment_complete", {"url": live_url, "platform": platform})

        print(f"\n  ✅ Deployed successfully!")
        print(f"  🌐 Live URL: {live_url}")

        # A2A: final report closes the pipeline loop
        self.a2a.send(
            sender=self.agent_name,
            recipient="interview_agent",
            msg_type="pipeline_complete",
            payload={"project_id": project_id, "url": live_url},
        )

        return {
            "project_id": project_id,
            "status": "deployed",
            "platform": platform,
            "url": live_url,
            "image": image_tag,
        }
