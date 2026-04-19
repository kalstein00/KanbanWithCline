from __future__ import annotations

import socket
import subprocess
import threading
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from shutil import which
from typing import Any, Literal
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
CLINE_PATH = which("cline")
CLINE_TIMEOUT_SECONDS = 120

RUN_STATUS_GROUPS = {
    "queue": {"draft", "planned"},
    "stream": {"running", "awaiting_review", "revising"},
    "synthesis": {"completed", "failed", "cancelled"},
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


class TaskCreate(BaseModel):
    title: str
    type: Literal[
        "document_analysis",
        "prd_generation",
        "debugging",
        "test_writing",
        "code_review",
        "refactor_planning",
    ]
    goal: str
    constraints: list[str] = Field(default_factory=list)
    priority: Literal["low", "medium", "high"] = "medium"
    mode: Literal["plan-execute-eval", "single-agent", "debate"] = "plan-execute-eval"
    relatedPaths: list[str] = Field(default_factory=list)


class RunCreate(BaseModel):
    action: Literal["start", "retry"] = "retry"
    useCline: bool = True


class RunAction(BaseModel):
    action: Literal["approve", "reopen", "cancel"]


class InMemoryStore:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.tasks: list[dict[str, Any]] = []
        self.runs_by_task_id: dict[str, list[dict[str, Any]]] = {}
        self._seed()

    def _seed(self) -> None:
        now = utc_now()
        tasks = [
            {
                "id": "task_001",
                "title": "Legacy design docs to product PRD conversion",
                "type": "prd_generation",
                "goal": "Analyze the existing concept docs and produce a product PRD with explicit run and artifact models.",
                "constraints": ["Keep the current visual language", "Preserve MVP scope"],
                "priority": "high",
                "relatedPaths": ["doc/PRODUCT-PRD.md", "doc/FRONTEND.md"],
                "createdAt": now,
                "latestRunId": "run_001",
                "latestRunStatus": "awaiting_review",
            },
            {
                "id": "task_002",
                "title": "FastAPI 500 error root cause isolation",
                "type": "debugging",
                "goal": "Reproduce the failure, isolate the root cause, and recommend the lowest-risk fix path.",
                "constraints": ["Do not mutate production data"],
                "priority": "high",
                "relatedPaths": ["main.py", "src/"],
                "createdAt": now,
                "latestRunId": "run_002",
                "latestRunStatus": "running",
            },
            {
                "id": "task_003",
                "title": "Service layer regression test coverage",
                "type": "test_writing",
                "goal": "Add missing tests around edge-case validation paths and failure responses.",
                "constraints": ["Avoid snapshot tests"],
                "priority": "medium",
                "relatedPaths": ["tests/"],
                "createdAt": now,
                "latestRunId": "run_003",
                "latestRunStatus": "completed",
            },
            {
                "id": "task_004",
                "title": "Architecture notes ingestion plan",
                "type": "document_analysis",
                "goal": "Summarize architecture notes and identify unresolved assumptions before implementation starts.",
                "constraints": ["Call out open issues explicitly"],
                "priority": "medium",
                "relatedPaths": ["doc/"],
                "createdAt": now,
                "latestRunId": "run_004",
                "latestRunStatus": "planned",
            },
        ]
        runs_by_task_id = {
            "task_001": [
                {
                    "id": "run_001",
                    "taskId": "task_001",
                    "mode": "plan-execute-eval",
                    "status": "awaiting_review",
                    "startedAt": now,
                    "endedAt": None,
                    "currentPhase": "eval",
                    "primaryAgentRole": "Evaluator",
                    "summary": "Evaluator flagged missing task-run relationship definitions and API path ambiguity.",
                    "runner": {"provider": "mock", "available": bool(CLINE_PATH), "commandPreview": None},
                    "steps": [
                        self._step("plan", "Planner", "completed", "Mapped legacy docs into product and frontend workstreams."),
                        self._step("execute", "Cline Executor", "completed", "Drafted product and frontend PRD documents."),
                        self._step("eval", "Evaluator", "completed", "Requested clearer ownership for task, run, artifact, and verdict entities."),
                    ],
                    "artifacts": [
                        self._artifact("document", "PRODUCT-PRD.md", "doc/PRODUCT-PRD.md", selected=True),
                        self._artifact("document", "FRONTEND.md", "doc/FRONTEND.md", selected=False),
                    ],
                    "verdict": {
                        "decision": "revise",
                        "reason": "The document structure is sound, but task-run ownership and endpoint semantics need to be locked before implementation.",
                        "risks": ["Frontend and backend may diverge on status ownership", "Retry and approval actions remain underspecified"],
                        "recommendedNextAction": "retry_with_critique",
                    },
                }
            ],
            "task_002": [
                {
                    "id": "run_002",
                    "taskId": "task_002",
                    "mode": "debate",
                    "status": "running",
                    "startedAt": now,
                    "endedAt": None,
                    "currentPhase": "execute",
                    "primaryAgentRole": "Cline Executor",
                    "summary": "Executor is tracing request lifecycles while a parallel evaluator watches for regression risks.",
                    "runner": {"provider": "mock", "available": bool(CLINE_PATH), "commandPreview": None},
                    "steps": [
                        self._step("plan", "Planner", "completed", "Generated two likely causes around serialization and dependency injection."),
                        self._step("execute", "Cline Executor", "running", "Inspecting server logs and reproducing the error against a local fixture."),
                        self._step("eval", "Evaluator", "pending", "Waiting for the executor patch candidate."),
                    ],
                    "artifacts": [self._artifact("log", "uvicorn trace summary", "logs/debug-trace.md", selected=True)],
                    "verdict": {
                        "decision": "pending",
                        "reason": "Execution is still underway.",
                        "risks": ["Root cause not confirmed yet"],
                        "recommendedNextAction": "continue_run",
                    },
                }
            ],
            "task_003": [
                {
                    "id": "run_003",
                    "taskId": "task_003",
                    "mode": "plan-execute-eval",
                    "status": "completed",
                    "startedAt": now,
                    "endedAt": now,
                    "currentPhase": "eval",
                    "primaryAgentRole": "Evaluator",
                    "summary": "Tests cover success, validation failure, and invalid state transitions.",
                    "runner": {"provider": "mock", "available": bool(CLINE_PATH), "commandPreview": None},
                    "steps": [
                        self._step("plan", "Planner", "completed", "Outlined core scenarios and edge cases."),
                        self._step("execute", "Cline Executor", "completed", "Added unit tests for validation and failure branches."),
                        self._step("eval", "Evaluator", "completed", "Approved result after checking missing flaky patterns."),
                    ],
                    "artifacts": [self._artifact("test", "service_test.py patch", "tests/service_test.py", selected=True)],
                    "verdict": {
                        "decision": "approved",
                        "reason": "The selected artifact meets the required test coverage and risk profile.",
                        "risks": ["Future schema changes may require fixture updates"],
                        "recommendedNextAction": "approve",
                    },
                }
            ],
            "task_004": [
                {
                    "id": "run_004",
                    "taskId": "task_004",
                    "mode": "single-agent",
                    "status": "planned",
                    "startedAt": now,
                    "endedAt": None,
                    "currentPhase": "plan",
                    "primaryAgentRole": "Planner",
                    "summary": "Task has been scoped but execution has not started.",
                    "runner": {"provider": "mock", "available": bool(CLINE_PATH), "commandPreview": None},
                    "steps": [self._step("plan", "Planner", "completed", "Captured the document set and expected output sections.")],
                    "artifacts": [],
                    "verdict": {
                        "decision": "queued",
                        "reason": "Waiting for execution.",
                        "risks": ["Assumptions in the notes may still be outdated"],
                        "recommendedNextAction": "start_run",
                    },
                }
            ],
        }
        self.tasks = tasks
        self.runs_by_task_id = runs_by_task_id

    def _step(self, phase: str, agent_role: str, status: str, summary: str) -> dict[str, Any]:
        return {
            "id": new_id("step"),
            "phase": phase,
            "agentRole": agent_role,
            "status": status,
            "summary": summary,
        }

    def _artifact(self, artifact_type: str, title: str, path: str, *, selected: bool = False, content: str | None = None) -> dict[str, Any]:
        return {
            "id": new_id("artifact"),
            "type": artifact_type,
            "title": title,
            "path": path,
            "selected": selected,
            "content": content,
            "createdAt": utc_now(),
        }

    def list_tasks(self) -> list[dict[str, Any]]:
        with self.lock:
            payload = []
            for task in self.tasks:
                run = self.get_run(task["latestRunId"])
                payload.append({**deepcopy(task), "latestRun": self.run_snapshot(run) if run else None})
            return payload

    def create_task(self, payload: TaskCreate) -> dict[str, Any]:
        with self.lock:
            task_id = new_id("task")
            run_id = new_id("run")
            now = utc_now()
            task = {
                "id": task_id,
                "title": payload.title.strip(),
                "type": payload.type,
                "goal": payload.goal.strip(),
                "constraints": [item.strip() for item in payload.constraints if item.strip()],
                "priority": payload.priority,
                "relatedPaths": [item.strip() for item in payload.relatedPaths if item.strip()],
                "createdAt": now,
                "latestRunId": run_id,
                "latestRunStatus": "draft",
            }
            run = {
                "id": run_id,
                "taskId": task_id,
                "mode": payload.mode,
                "status": "draft",
                "startedAt": now,
                "endedAt": None,
                "currentPhase": "plan",
                "primaryAgentRole": "Planner",
                "summary": "Task is queued. Planner context is waiting for execution.",
                "runner": {"provider": "cline" if CLINE_PATH else "mock", "available": bool(CLINE_PATH), "commandPreview": None},
                "steps": [self._step("plan", "Planner", "pending", "Planning has not started yet.")],
                "artifacts": [],
                "verdict": {
                    "decision": "queued",
                    "reason": "No execution has started yet.",
                    "risks": ["Context may still be incomplete"],
                    "recommendedNextAction": "start_run",
                },
            }
            self.tasks.insert(0, task)
            self.runs_by_task_id[task_id] = [run]
            return deepcopy(task)

    def get_task(self, task_id: str) -> dict[str, Any]:
        task = next((item for item in self.tasks if item["id"] == task_id), None)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    def list_runs(self, task_id: str) -> list[dict[str, Any]]:
        with self.lock:
            self.get_task(task_id)
            return deepcopy(self.runs_by_task_id.get(task_id, []))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        for runs in self.runs_by_task_id.values():
            for run in runs:
                if run["id"] == run_id:
                    return run
        return None

    def get_run_or_404(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    def run_snapshot(self, run: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": run["id"],
            "status": run["status"],
            "mode": run["mode"],
            "currentPhase": run["currentPhase"],
            "primaryAgentRole": run["primaryAgentRole"],
            "summary": run["summary"],
        }

    def create_run(self, task_id: str, payload: RunCreate) -> dict[str, Any]:
        with self.lock:
            task = self.get_task(task_id)
            previous_run = self.get_run_or_404(task["latestRunId"])
            run_id = new_id("run")
            command_preview = build_cline_command_preview(task, previous_run["mode"])
            status = "running" if payload.action == "start" else "revising"
            run = {
                "id": run_id,
                "taskId": task_id,
                "mode": previous_run["mode"],
                "status": status,
                "startedAt": utc_now(),
                "endedAt": None,
                "currentPhase": "execute",
                "primaryAgentRole": "Cline Executor" if payload.useCline and CLINE_PATH else "Executor",
                "summary": "Cline executor is preparing the next attempt." if payload.useCline and CLINE_PATH else "Execution restarted without a live Cline invocation.",
                "runner": {
                    "provider": "cline" if payload.useCline and CLINE_PATH else "mock",
                    "available": bool(CLINE_PATH),
                    "commandPreview": command_preview,
                },
                "steps": [
                    self._step("plan", "Planner", "completed", "Reframed the goal and constraints for the next run."),
                    self._step("execute", "Cline Executor" if payload.useCline and CLINE_PATH else "Executor", "running", "Execution is in progress."),
                    self._step("eval", "Evaluator", "pending", "Waiting for artifacts from the new run."),
                ],
                "artifacts": [],
                "verdict": {
                    "decision": "pending",
                    "reason": "The run is still in progress.",
                    "risks": ["Fresh evidence has not been reviewed yet"],
                    "recommendedNextAction": "continue_run",
                },
            }
            self.runs_by_task_id.setdefault(task_id, []).insert(0, run)
            task["latestRunId"] = run_id
            task["latestRunStatus"] = status
        if payload.useCline and CLINE_PATH:
            self.start_cline_run(task_id, run_id)
        return deepcopy(run)

    def patch_run(self, run_id: str, payload: RunAction) -> dict[str, Any]:
        with self.lock:
            run = self.get_run_or_404(run_id)
            task = self.get_task(run["taskId"])
            if payload.action == "approve":
                run["status"] = "completed"
                run["endedAt"] = utc_now()
                run["currentPhase"] = "eval"
                run["primaryAgentRole"] = "Evaluator"
                run["summary"] = "Run approved from the workbench."
                run["verdict"] = {
                    "decision": "approved",
                    "reason": "The current result was approved by the user.",
                    "risks": ["Manual approval does not guarantee downstream merge readiness"],
                    "recommendedNextAction": "approved",
                }
                if run["steps"]:
                    run["steps"][-1]["status"] = "completed"
                    run["steps"][-1]["summary"] = "User approved the run."
            elif payload.action == "reopen":
                run["status"] = "planned"
                run["endedAt"] = None
                run["currentPhase"] = "plan"
                run["primaryAgentRole"] = "Planner"
                run["summary"] = "Run moved back to planning for another pass."
                run["verdict"] = {
                    "decision": "queued",
                    "reason": "The user requested a reopened planning cycle.",
                    "risks": ["Previous artifacts may now be stale"],
                    "recommendedNextAction": "start_run",
                }
                run["steps"] = [self._step("plan", "Planner", "pending", "Planning will resume when the task is started again.")]
            else:
                run["status"] = "cancelled"
                run["endedAt"] = utc_now()
                run["currentPhase"] = "eval"
                run["primaryAgentRole"] = "Evaluator"
                run["summary"] = "Run was cancelled from the workbench."
                run["verdict"] = {
                    "decision": "cancelled",
                    "reason": "The user stopped the run before completion.",
                    "risks": ["Partial artifacts may not be actionable"],
                    "recommendedNextAction": "retry",
                }
            task["latestRunId"] = run["id"]
            task["latestRunStatus"] = run["status"]
            return deepcopy(run)

    def start_cline_run(self, task_id: str, run_id: str) -> None:
        thread = threading.Thread(target=self._execute_cline_run, args=(task_id, run_id), daemon=True)
        thread.start()

    def _execute_cline_run(self, task_id: str, run_id: str) -> None:
        if not CLINE_PATH:
            return
        task = self.get_task(task_id)
        run = self.get_run_or_404(run_id)
        prompt = build_cline_prompt(task, run)
        command = [
            CLINE_PATH,
            "task",
            "--json",
            "--yolo",
            "--cwd",
            str(BASE_DIR),
            prompt,
        ]
        with self.lock:
            run["runner"]["commandPreview"] = " ".join(command)
            run["summary"] = "Cline is executing the requested task."
            run["artifacts"].append(self._artifact("command", "Cline command preview", "", selected=False, content=" ".join(command)))
        try:
            result = subprocess.run(
                command,
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=CLINE_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            with self.lock:
                self._mark_run_failed(run_id, "Cline timed out before producing a reviewable result.", "timeout")
            return
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        content = stdout or stderr or "Cline finished without emitting output."
        with self.lock:
            current_run = self.get_run_or_404(run_id)
            current_run["artifacts"].append(
                self._artifact(
                    "transcript" if result.returncode == 0 else "log",
                    "Cline session output",
                    "",
                    selected=result.returncode == 0,
                    content=content,
                )
            )
            if result.returncode == 0:
                current_run["status"] = "awaiting_review"
                current_run["endedAt"] = utc_now()
                current_run["currentPhase"] = "eval"
                current_run["primaryAgentRole"] = "Evaluator"
                current_run["summary"] = "Cline completed execution. Review is required before approval."
                current_run["verdict"] = {
                    "decision": "review_required",
                    "reason": "Execution finished and the transcript is available for inspection.",
                    "risks": ["CLI output may still need manual validation"],
                    "recommendedNextAction": "approve_or_retry",
                }
                current_run["steps"][1]["status"] = "completed"
                current_run["steps"][1]["summary"] = "Cline execution finished successfully."
                current_run["steps"][2]["status"] = "completed"
                current_run["steps"][2]["summary"] = "Awaiting human review in the workbench."
            else:
                self._mark_run_failed(run_id, "Cline returned a non-zero exit code.", f"exit:{result.returncode}")
            task = self.get_task(task_id)
            task["latestRunStatus"] = current_run["status"]

    def _mark_run_failed(self, run_id: str, reason: str, code: str) -> None:
        run = self.get_run_or_404(run_id)
        run["status"] = "failed"
        run["endedAt"] = utc_now()
        run["currentPhase"] = "eval"
        run["primaryAgentRole"] = "Evaluator"
        run["summary"] = reason
        run["verdict"] = {
            "decision": "retry",
            "reason": f"{reason} ({code})",
            "risks": ["No accepted artifact was produced"],
            "recommendedNextAction": "retry",
        }
        if len(run["steps"]) > 1:
            run["steps"][1]["status"] = "failed"
            run["steps"][1]["summary"] = reason
        if len(run["steps"]) > 2:
            run["steps"][2]["status"] = "completed"
            run["steps"][2]["summary"] = "Evaluator marked the run as failed."
        task = self.get_task(run["taskId"])
        task["latestRunStatus"] = "failed"


def build_cline_prompt(task: dict[str, Any], run: dict[str, Any]) -> str:
    constraints = "\n".join(f"- {item}" for item in task["constraints"]) or "- None provided"
    paths = "\n".join(f"- {item}" for item in task.get("relatedPaths", [])) or "- None provided"
    return (
        "You are operating inside the KanbanWithCline workbench.\n"
        f"Task title: {task['title']}\n"
        f"Task type: {task['type']}\n"
        f"Goal: {task['goal']}\n"
        f"Mode: {run['mode']}\n"
        "Constraints:\n"
        f"{constraints}\n"
        "Relevant paths:\n"
        f"{paths}\n"
        "Return a concise execution summary with evidence, risks, and next recommended action."
    )


def build_cline_command_preview(task: dict[str, Any], mode: str) -> str | None:
    if not CLINE_PATH:
        return None
    prompt = build_cline_prompt(task, {"mode": mode})
    preview = [CLINE_PATH, "task", "--json", "--yolo", "--cwd", str(BASE_DIR), prompt]
    return " ".join(preview)


store = InMemoryStore()
app = FastAPI()


@app.get("/api/meta")
def get_meta() -> dict[str, Any]:
    return {
        "clineAvailable": bool(CLINE_PATH),
        "clinePath": CLINE_PATH,
        "timeoutSeconds": CLINE_TIMEOUT_SECONDS,
        "statusGroups": {key: sorted(value) for key, value in RUN_STATUS_GROUPS.items()},
    }


@app.get("/api/tasks")
def list_tasks() -> list[dict[str, Any]]:
    return store.list_tasks()


@app.post("/api/tasks")
def create_task(payload: TaskCreate) -> dict[str, Any]:
    return store.create_task(payload)


@app.get("/api/tasks/{task_id}/runs")
def list_task_runs(task_id: str) -> list[dict[str, Any]]:
    return store.list_runs(task_id)


@app.post("/api/tasks/{task_id}/runs")
def create_task_run(task_id: str, payload: RunCreate) -> dict[str, Any]:
    return store.create_run(task_id, payload)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    return deepcopy(store.get_run_or_404(run_id))


@app.get("/api/runs/{run_id}/artifacts")
def get_run_artifacts(run_id: str) -> list[dict[str, Any]]:
    run = store.get_run_or_404(run_id)
    return deepcopy(run["artifacts"])


@app.get("/api/runs/{run_id}/verdict")
def get_run_verdict(run_id: str) -> dict[str, Any]:
    run = store.get_run_or_404(run_id)
    return deepcopy(run["verdict"])


@app.patch("/api/runs/{run_id}")
def patch_run(run_id: str, payload: RunAction) -> dict[str, Any]:
    return store.patch_run(run_id, payload)


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


def get_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        sock.close()
    return ip


if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8000
    print("\n" + "=" * 50)
    print("Kanban Web App is running.")
    print(f"Access URL: http://{local_ip}:{port}")
    print("=" * 50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
