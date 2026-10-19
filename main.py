"""
ProjectDNA — Command Line Runner
Execute the multi-agent pipeline from the terminal.
"""

from __future__ import annotations
import sys
import argparse
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from project_dna import ProjectDNAPipeline, DNAParser


def run_sample(dna_path: str, export_dir: str | None = None) -> None:
    path = Path(dna_path)
    if not path.exists():
        print(f"Error: DNA file not found: {dna_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading and executing DNA file: {path.name}")
    pipeline = ProjectDNAPipeline()
    result = pipeline.run_from_dna(path)
    print(f"\nFinal Result: {result.get('pipeline_status')}")

    if export_dir and result.get("pipeline_status") == "complete":
        written = pipeline.export_files(export_dir)
        print(f"\n📁 Exported {len(written)} files to: {Path(export_dir).resolve()}")


def run_validate_only(dna_path: str) -> None:
    path = Path(dna_path)
    if not path.exists():
        print(f"Error: DNA file not found: {dna_path}", file=sys.stderr)
        sys.exit(1)

    parser = DNAParser()
    dna = parser.load(path)
    is_valid, missing = parser.validate()

    print(f"\n=== DNA Validation for {path.name} ===")
    print(f"Project Name : {dna.project.name}")
    print(f"Is Valid     : {'✅ PASSED' if is_valid else '❌ FAILED'}")

    if not is_valid:
        print(f"\nMissing mandatory fields ({len(missing)}):")
        for f in missing:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("All mandatory fields are present and valid.")


def run_interactive() -> None:
    from project_dna.agents import InterviewAgent
    print("\n" + "=" * 60)
    print("🧬 ProjectDNA Interactive Interview")
    print("Press Enter to use default demo answer if empty.")
    print("=" * 60)

    defaults = {
        "project.name": "TodoFlow",
        "project.description": "A todo app with AI task prioritization",
        "project.vision": "Help users focus on the right tasks at the right time",
        "project.problem.statement": "Users have too many tasks and cannot prioritize them",
        "project.goals.primary_goal": "Users can add tasks and AI ranks them by urgency",
        "project.goals.success_metrics": "Task creation works in under 2 seconds, AI prioritization runs on every task add, UI is mobile responsive",
        "project.tech_stack.frontend": "React + Tailwind CSS",
        "project.tech_stack.backend": "FastAPI Python",
        "project.tech_stack.database": "SQLite",
        "project.security.auth": "JWT tokens",
        "project.tools.allowed_tools": "file_write, bash_execute, git_commit",
        "project.output_requirements.must_include": "Task creation form, AI priority ranking display, Mobile responsive layout",
        "project.deployment": "Vercel",
    }

    answers = {}
    for key, prompt in InterviewAgent.QUESTIONS:
        default_val = defaults.get(key, "")
        user_val = input(f"\n{prompt}\n[Default: {default_val}]: ").strip()
        answers[key] = user_val if user_val else default_val

    pipeline = ProjectDNAPipeline()
    result = pipeline.run(answers)
    print(f"\nFinal Result: {result.get('pipeline_status')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ProjectDNA — Multi-Agent Software Engineering Orchestrator"
    )
    parser.add_argument(
        "dna_file",
        nargs="?",
        default="samples/todoflow.dna",
        help="Path to .dna YAML specification file (default: samples/todoflow.dna)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate a .dna file without executing the pipeline",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run interactive interview questions to construct DNA",
    )
    parser.add_argument(
        "--export",
        metavar="DIR",
        default=None,
        help="Export generated codebase files to a physical directory (e.g. --export ./output)",
    )

    args = parser.parse_args()

    if args.interactive:
        run_interactive()
    elif args.validate_only:
        run_validate_only(args.dna_file)
    else:
        run_sample(args.dna_file, export_dir=args.export)


if __name__ == "__main__":
    main()
