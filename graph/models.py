"""Pydantic models for the canonical trace JSON (CLAUDE.md section 6)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Argument(BaseModel):
    name: str
    value: Any
    valid: bool = True
    violation: str | None = None
    refers_to: str | None = None


class ToolCall(BaseModel):
    id: str
    tool: str
    attempt: int = 1
    status: Literal["ok", "error", "timeout", "unavailable"] = "ok"
    latency_ms: int = 100
    args: list[Argument] = Field(default_factory=list)


class ToolError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class Observation(BaseModel):
    id: str
    status: Literal["ok", "error"] = "ok"
    summary: str = ""
    error: ToolError | None = None


class Evidence(BaseModel):
    id: str
    text: str
    source_type: str = "tool"
    stale: bool = False
    about: list[str] = Field(default_factory=list)


class Step(BaseModel):
    idx: int
    kind: Literal["tool", "answer"]
    stated_rationale: str | None = None
    tool_call: ToolCall | None = None
    observation: Observation | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class Claim(BaseModel):
    key: str
    value: str
    supported_by: list[str] = Field(default_factory=list)


class FinalAnswer(BaseModel):
    text: str
    acknowledges_limitation: bool = False
    claims: list[Claim] = Field(default_factory=list)


class Label(BaseModel):
    injected_pattern: str | None = None
    root_cause_step: int | None = None
    contributing: list[str] = Field(default_factory=list)


class Agent(BaseModel):
    version: str = "1.3.0"
    prompt_version: str = "p4"
    model: str = "scripted"


class Trace(BaseModel):
    run_id: str
    session_id: str
    task_id: str
    agent: Agent = Field(default_factory=Agent)
    user_request: str
    steps: list[Step]
    final_answer: FinalAnswer
    label: Label = Field(default_factory=Label)
