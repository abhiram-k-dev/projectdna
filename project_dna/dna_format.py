"""
ProjectDNA — DNA File Format Specification
Pydantic models defining the .dna YAML schema (version 1.0)
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProblemModel(BaseModel):
    statement: str = ""
    why_it_exists: str = ""


class UsersModel(BaseModel):
    primary_users: List[str] = Field(default_factory=list)
    secondary_users: List[str] = Field(default_factory=list)


class GoalsModel(BaseModel):
    primary_goal: str = ""
    success_metrics: List[str] = Field(default_factory=list)


class ConstraintsModel(BaseModel):
    time_limit: str = ""
    budget_limit: str = ""
    technical_limits: List[str] = Field(default_factory=list)


class TechStackModel(BaseModel):
    frontend: str = ""
    backend: str = ""
    database: str = ""
    ai_models: List[str] = Field(default_factory=list)
    infra: str = ""


class ArchitectureModel(BaseModel):
    pattern: str = ""
    structure_rules: List[str] = Field(default_factory=list)


class AIBehaviorModel(BaseModel):
    reasoning_style: str = ""
    agent_mode: bool = True


class AgentDefModel(BaseModel):
    enabled: bool = True
    responsibilities: List[str] = Field(default_factory=list)


class AgentsModel(BaseModel):
    planner_agent: AgentDefModel = Field(default_factory=AgentDefModel)
    builder_agent: AgentDefModel = Field(default_factory=AgentDefModel)
    tester_agent: AgentDefModel = Field(default_factory=AgentDefModel)
    security_agent: AgentDefModel = Field(default_factory=AgentDefModel)


class MemoryModel(BaseModel):
    type: str = ""
    storage: str = ""


class ToolsModel(BaseModel):
    allowed_tools: List[str] = Field(default_factory=list)
    forbidden_tools: List[str] = Field(default_factory=list)


class SecurityModel(BaseModel):
    auth: str = ""
    permissions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    guardrails: List[str] = Field(default_factory=list)


class TestingModel(BaseModel):
    unit_tests: bool = True
    integration_tests: bool = True
    evaluation_strategy: str = ""


class OutputRequirementsModel(BaseModel):
    format: str = ""
    must_include: List[str] = Field(default_factory=list)


class ProjectModel(BaseModel):
    name: str = ""
    description: str = ""
    vision: str = ""
    problem: ProblemModel = Field(default_factory=ProblemModel)
    users: UsersModel = Field(default_factory=UsersModel)
    goals: GoalsModel = Field(default_factory=GoalsModel)
    constraints: ConstraintsModel = Field(default_factory=ConstraintsModel)
    tech_stack: TechStackModel = Field(default_factory=TechStackModel)
    architecture: ArchitectureModel = Field(default_factory=ArchitectureModel)
    ai_behavior: AIBehaviorModel = Field(default_factory=AIBehaviorModel)
    agents: AgentsModel = Field(default_factory=AgentsModel)
    memory: MemoryModel = Field(default_factory=MemoryModel)
    tools: ToolsModel = Field(default_factory=ToolsModel)
    security: SecurityModel = Field(default_factory=SecurityModel)
    testing: TestingModel = Field(default_factory=TestingModel)
    deployment: str = ""
    output_requirements: OutputRequirementsModel = Field(default_factory=OutputRequirementsModel)
    rules: List[str] = Field(default_factory=lambda: [
        "No hallucinated features",
        "Follow architecture strictly",
        "Fail fast on missing requirements",
        "Never skip security guardrails",
        "Eval before every deployment",
    ])


class DNAFile(BaseModel):
    """Root model for a .dna file — the single source of truth."""
    project_dna_version: str = "1.0"
    project: ProjectModel = Field(default_factory=ProjectModel)
    extensions: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


# ------------------------------------------------------------------ #
# MANDATORY FIELDS — kept outside the model so Pydantic V2 ignores it #
# ------------------------------------------------------------------ #
DNA_MANDATORY_PATHS: List[str] = [
    "project.name",
    "project.description",
    "project.vision",
    "project.problem.statement",
    "project.goals.primary_goal",
    "project.goals.success_metrics",
    "project.tech_stack.backend",
    "project.security.auth",
    "project.tools.allowed_tools",
    "project.output_requirements.must_include",
]
