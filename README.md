# 🧬 ProjectDNA

**ProjectDNA** is an autonomous multi-agent software engineering framework that turns structured software specifications (`.dna` files) into validated, built, evaluated, and deployed applications.

Built around Google ADK agent patterns, Model Context Protocol (MCP) server abstractions, and zero-trust blocking guardrails, ProjectDNA enforces architectural discipline, prevents hallucinations, and delivers measurable token efficiency through context slicing.

---

## 📑 Table of Contents

- [Core Highlights](#-core-highlights)
- [Architecture & Agent Workflow](#-architecture--agent-workflow)
- [Security Guardrails](#-security-guardrails)
- [MCP Servers](#-mcp-servers)
- [Installation](#-installation)
- [How to Run](#-how-to-run)
  - [1. Quick Start (Default Demo)](#1-quick-start-default-demo)
  - [2. Run with Existing DNA File](#2-run-with-an-existing-dna-file)
  - [3. Validate a DNA File](#3-validate-a-dna-file)
  - [4. Interactive Interview Mode](#4-interactive-interview-mode)
  - [5. Programmatic Python API](#5-programmatic-python-api)
  - [6. Running Tests](#6-running-tests)
- [Project Directory Structure](#-project-directory-structure)
- [DNA File Specification (.dna)](#-dna-file-specification-dna)

---

## 🌟 Core Highlights

- **Single Source of Truth (`.dna`)**: Every requirement, goal, metric, tech stack choice, tool permission, and deployment rule is declared in a YAML `.dna` file.
- **Context Slicing (~70%–90% Token Savings)**: Rather than dumping the entire project spec into every agent's prompt, each agent receives only its relevant slice (e.g., Planner gets goals/tech stack, Eval gets success metrics/rules).
- **6 Blocking Pre-Hook Guardrails**: Deterministic safety checks run *before* any tool execution. Disallowed actions, hardcoded secrets, scope creep, and unverified deployments are halted immediately.
- **Agent-to-Agent (A2A) Communication**: Agents hand off execution state via structured directed messages with full trajectory logging.
- **Simulated MCP Server Layer**: Filesystem, GitHub, Docker, and Database operations are routed through standardized MCP interfaces.

---

## 🏗️ Architecture & Agent Workflow

The pipeline operates as a state machine where each agent represents a node and A2A messages represent directed edges:

```
┌─────────────────┐       A2A: stage_complete
│ Interview Agent │ ───────────────────────────────┐
└─────────────────┘                                │
        │ (generates .dna)                         ▼
┌──────────────────┐      A2A: stage_complete     ┌─────────────────┐
│  Validator Agent │ ───────────────────────────> │  Planner Agent  │
└──────────────────┘                              └─────────────────┘
        │ (blocks if invalid)                              │ A2A: stage_complete
        ▼                                                  ▼
┌──────────────────┐      A2A: stage_complete     ┌─────────────────┐
│ Deployment Agent │ <─────────────────────────── │   Builder Agent │
└──────────────────┘                              └─────────────────┘
        ▲                                                  │ A2A: stage_complete
        │                                                  ▼
        │                 A2A: stage_complete     ┌─────────────────┐
        └──────────────────────────────────────── │   Eval Agent    │
                     (Eval Gate Check)            └─────────────────┘
```

### The 6 Specialized Agents

| Agent | Responsibility | Context Slice Received |
|---|---|---|
| **InterviewAgent** | Conducts structured requirements interviews, synthesizes responses into `.dna` schema, and writes it to DB and Filesystem MCP. | Empty template / User input |
| **ValidatorAgent** | Performs strict schema checks on mandatory fields, detects ambiguous metrics (e.g. "fast", "simple"), and flags missing auth or guardrails. | `project` (full project metadata) |
| **PlannerAgent** | Breaks requirements into discrete stages (scaffold, backend API, frontend deliverables) with actionable tasks and outputs. | `project.goals`, `project.constraints`, `project.tech_stack` |
| **BuilderAgent** | Executes planned stages: generates backend/frontend code, enforces security/scope guardrails, writes files, and creates Git commits. | `project.tech_stack`, `project.architecture`, `project.tools`, `project.rules` |
| **EvalAgent** | Evaluates generated code against declared success metrics and validates trajectory history before deployment. | `project.goals.success_metrics`, `project.rules` |
| **DeploymentAgent** | Verifies the eval gate pass, triggers container build via Docker MCP, and deploys to target cloud platform (e.g., Vercel, Cloud Run). | `project.deployment`, `project.tools` |

---

## 🛡️ Security Guardrails

All guardrails run deterministically as blocking pre-hooks:

1. **Secret Detection Hook**: Scans every code generation payload for sensitive tokens (OpenAI keys, Google API keys, database connection strings, PEM private keys, bearer tokens) and blocks unauthorized writes.
2. **Tool Permission Hook**: Checks if the requested tool (`file_write`, `bash_execute`, etc.) is in the project's `allowed_tools` whitelist.
3. **Scope Enforcement Hook**: Prevents feature hallucinations and scope creep by ensuring the Builder Agent only implements features declared in `output_requirements.must_include`.
4. **Eval Gate Hook**: Strictly blocks `DeploymentAgent` unless `EvalAgent` has recorded an `eval_passed` status in memory.
5. **Context Size Limit Hook**: Validates that prompt context size remains within token quotas.
6. **DNA Mutation Guard Hook**: Restricts editing or generating `.dna` specification files strictly to `InterviewAgent`.

---

## 🔌 MCP Servers

ProjectDNA implements simulated Model Context Protocol servers:

- **`FilesystemMCP`**: Sandboxed virtual file system (`read_file`, `write_file`, `list_directory`, `delete_file`).
- **`GitHubMCP`**: Version control simulation (`git_commit`, `git_log`, `get_branch`).
- **`DockerMCP`**: Container engine simulation (`docker_build`, `cloud_run_deploy`).
- **`DatabaseMCP`**: Persistent key-value store, trajectory logs, and DNA registry.

---

## 📦 Installation

### Prerequisites

- Python **3.9** or higher

### Setup

1. **Clone or navigate to the repository directory**:
   ```bash
   cd projectdna-package
   ```

2. **(Recommended) Create and activate a virtual environment**:
   - On Windows (PowerShell):
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   - On Linux / macOS:
     ```bash
     python -m venv venv
     source venv/bin/activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. *(Optional)* Install in editable mode:
   ```bash
   pip install -e .
   ```

---

## 🚀 How to Run

### 1. Quick Start (Default Demo)

To run the pipeline using the included default sample (`samples/todoflow.dna`):

```bash
python main.py
```

This will:
- Load the TodoFlow specification.
- Run validation checks.
- Generate a 3-stage execution plan.
- Scaffold the project, backend API, and frontend components.
- Run secret detection demonstrations (showing intentional blocking of unsafe code).
- Run evaluation against success metrics.
- Build Docker container and deploy to Vercel (simulated).

---

### 2. Run with an Existing DNA File

Pass any `.dna` specification file directly as an argument:

```bash
python main.py samples/todoflow.dna
```

Or run the blog platform sample:

```bash
python main.py samples/blogapp.dna
```

---

### 3. Validate a DNA File

To check whether a `.dna` file satisfies all mandatory schema fields without running full code generation:

```bash
python main.py --validate-only samples/todoflow.dna
```

Test against an incomplete specification to inspect validation errors:

```bash
python main.py --validate-only samples/invalid_missing_fields.dna
```

---

### 4. Interactive Interview Mode

To conduct an interactive questionnaire where the Interview Agent prompts you for project details and synthesizes the `.dna` specification dynamically:

```bash
python main.py --interactive
```

*(Press Enter on any prompt to accept default sample values).*

---

### 5. Programmatic Python API

You can import and use ProjectDNA directly in your Python code:

#### Run from an existing `.dna` file:
```python
from project_dna import ProjectDNAPipeline

pipeline = ProjectDNAPipeline()
result = pipeline.run_from_dna("samples/todoflow.dna")

print("Pipeline Status:", result["pipeline_status"])
print("Live URL:", result.get("deployment", {}).get("url"))
print("Generated Files:", len(result["generated_files"]))
```

#### Run with interview answers dictionary:
```python
from project_dna import ProjectDNAPipeline

answers = {
    "project.name": "QuickTask",
    "project.description": "Minimalist task tracking app",
    "project.vision": "Frictionless personal productivity",
    "project.problem.statement": "Existing task apps are bloated",
    "project.goals.primary_goal": "Fast creation of daily todo lists",
    "project.goals.success_metrics": "Load time < 1s, One-click creation",
    "project.tech_stack.frontend": "React",
    "project.tech_stack.backend": "FastAPI",
    "project.tech_stack.database": "SQLite",
    "project.security.auth": "JWT",
    "project.tools.allowed_tools": "file_write, git_commit",
    "project.output_requirements.must_include": "Task creation form, Task list view",
    "project.deployment": "Cloud Run",
}

pipeline = ProjectDNAPipeline()
result = pipeline.run(answers)
print("Pipeline Result:", result["pipeline_status"])
```

#### Parse and slice context manually:
```python
from project_dna import DNAParser

parser = DNAParser()
dna = parser.load("samples/todoflow.dna")

# Context slice for planner
planner_ctx = parser.get_agent_context("planner_agent")
print("Planner Context Slice:", planner_ctx["context"])
print("Token Savings:", planner_ctx["token_savings_vs_full"])
```

---

### 6. Running Tests

Run the test suite using `pytest`:

```bash
python -m pytest
```

Output:
```text
============================= test session starts =============================
collected 7 items

tests/test_project_dna.py .......                                        [100%]

============================== 7 passed in 0.31s ==============================
```

> **Windows PowerShell Tip:**
> If you encounter character encoding issues (`charmap` error) when printing Unicode emojis in raw custom scripts, enable UTF-8 mode by running:
> ```powershell
> $env:PYTHONUTF8 = "1"
> ```
> `main.py` handles this automatically for you.

---

## 📁 Project Directory Structure

```text
projectdna-package/
├── main.py                  # CLI runner script (run, validate, interactive)
├── requirements.txt         # Package dependencies
├── pyproject.toml           # Packaging metadata
├── pytest.ini               # Pytest configuration
├── README.md                # Project documentation
│
├── project_dna/             # Core ProjectDNA package
│   ├── __init__.py          # Public API exports
│   ├── dna_format.py        # Pydantic v2 models for .dna schema & mandatory paths
│   ├── dna_parser.py        # YAML parser & agent context slicing
│   ├── guardrails.py        # 6 blocking pre-hook guardrail checks
│   ├── mcp_servers.py       # Simulated MCP Servers (Filesystem, GitHub, Docker, DB)
│   ├── agents.py            # 6 ADK agents & A2A message bus
│   └── pipeline.py          # State graph orchestrator (LangGraph pattern)
│
├── samples/                 # Sample specification files
│   ├── todoflow.dna         # Complete valid TodoFlow project specification
│   ├── blogapp.dna          # Complete valid BlogForge project specification
│   └── invalid_missing_fields.dna  # Incomplete spec demonstrating validation failure
│
└── tests/                   # Test suite
    └── test_project_dna.py  # Unit tests for parser, guardrails, and pipeline
```

---

## 📜 DNA File Specification (`.dna`)

A `.dna` file is a structured YAML specification adhering to schema version 1.0. Mandatory fields include:

- `project.name`
- `project.description`
- `project.vision`
- `project.problem.statement`
- `project.goals.primary_goal`
- `project.goals.success_metrics` (minimum 1 measurable metric)
- `project.tech_stack.backend`
- `project.security.auth`
- `project.tools.allowed_tools`
- `project.output_requirements.must_include`

Refer to [samples/todoflow.dna](samples/todoflow.dna) for a complete reference implementation.

---

## 📄 License

MIT License. Developed for autonomous agentic software engineering research.
