from __future__ import annotations

import atexit
import socket
import json
import os
import queue
import subprocess
import signal
import sys
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from shutil import which
from typing import Any, Literal
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RUN_LOG_DIR = BASE_DIR / "logs" / "runs"
SYSTEM_LOG_DIR = BASE_DIR / "logs" / "system"
STATE_DIR = BASE_DIR / "logs" / "state"
STATE_PATH = STATE_DIR / "workbench-state.json"
CLINE_PATH = which("cline")
CLINE_TIMEOUT_SECONDS = 120
MAX_RUN_LOG_FILES = 5

RUN_STATUS_GROUPS = {
    "queue": {"draft", "planned"},
    "stream": {"running", "awaiting_review", "revising"},
    "synthesis": {"completed", "failed", "cancelled", "orphaned"},
}


class LifecycleTracker:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.shutdown_reason = "unknown"
        self.shutdown_signal: str | None = None
        self.exit_code: int | None = None
        self.signal_handlers_installed = False

    def mark_shutdown(self, reason: str, *, signame: str | None = None, exit_code: int | None = None) -> None:
        with self.lock:
            self.shutdown_reason = reason
            if signame:
                self.shutdown_signal = signame
            if exit_code is not None:
                self.exit_code = exit_code

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "reason": self.shutdown_reason,
                "signal": self.shutdown_signal,
                "exitCode": self.exit_code,
                "pid": os.getpid(),
                "ppid": os.getppid(),
            }


lifecycle = LifecycleTracker()


def local_now() -> datetime:
    return datetime.now().astimezone()


def local_now_iso() -> str:
    return local_now().isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def trim_text(value: str, *, limit: int = 400) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def sanitize_event_raw(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    payload: dict[str, Any] = {}
    for key in ("type", "say", "taskId", "ts", "partial", "conversationHistoryIndex"):
        if key in raw:
            payload[key] = raw[key]
    if "text" in raw and raw["text"]:
        payload["text"] = trim_text(str(raw["text"]), limit=240)
    if "line" in raw and raw["line"]:
        payload["line"] = trim_text(str(raw["line"]), limit=240)
    if "modelInfo" in raw:
        payload["modelInfo"] = raw["modelInfo"]
    if not payload:
        return {"preview": trim_text(str(raw), limit=240)}
    return payload


def parse_tool_payload(text: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def summarize_tool_payload(payload: dict[str, Any] | None, fallback_text: str) -> tuple[str, str]:
    if not payload:
        return trim_text(fallback_text or "Tool invocation recorded."), "tool_trace"

    tool_name = payload.get("tool") or payload.get("toolName") or "tool"
    path = payload.get("path") or payload.get("filePath") or payload.get("content") or ""

    if tool_name == "readFile":
        start = payload.get("readLineStart")
        end = payload.get("readLineEnd")
        line_range = f" ({start}-{end})" if start and end else ""
        return f"Read file: {path}{line_range}", "file_read"
    if tool_name in {"writeToFile", "editedExistingFile"}:
        return f"Modified file: {path}", "file_write"
    if tool_name in {"executeCommand", "runCommand"}:
        return f"Executed command: {trim_text(str(payload.get('command') or path), limit=120)}", "command_exec"
    if tool_name == "searchFiles":
        return f"Searched files: {trim_text(str(payload.get('regex') or payload.get('query') or path), limit=120)}", "search"
    if tool_name == "listFiles":
        return f"Listed files: {trim_text(str(path or payload.get('directoryPath') or '/'), limit=120)}", "list"

    return f"{tool_name}: {trim_text(str(path or fallback_text), limit=120)}", "tool_trace"


def summarize_evidence(run: dict[str, Any], *, limit: int = 4) -> list[str]:
    evidence: list[str] = []
    verdict = run.get("verdict") or {}
    if verdict.get("reason"):
        evidence.append(f"Verdict: {trim_text(str(verdict['reason']), limit=180)}")
    for event in reversed(run.get("events", [])):
        summary = event.get("summary")
        if not summary:
            continue
        evidence.append(f"{event.get('type', 'event')}: {trim_text(str(summary), limit=180)}")
        if len(evidence) >= limit:
            break
    return evidence


def infer_failure_analysis(run: dict[str, Any], *, code: str | None = None, reason: str | None = None) -> dict[str, Any] | None:
    status = run.get("status")
    verdict = run.get("verdict") or {}
    summary = reason or verdict.get("reason") or run.get("summary") or ""
    if status not in {"failed", "cancelled", "orphaned"} and verdict.get("decision") not in {"retry", "cancelled"}:
        return None

    lowered = summary.lower()
    failure_stage = run.get("currentPhase") or "eval"
    failure_type = "evaluation_failure"
    skill_gap = "failure-analysis"
    root_cause = "The run ended without a satisfactory verified outcome."
    recommended_fix = "Review the evaluator findings, update the task instructions, and retry with the missing guardrails."
    skill_seed = "Create a post-run evaluator skill that turns repeated failures into reusable checks."

    if status == "orphaned" or "orphan" in lowered:
        failure_stage = "execute"
        failure_type = "orphaned"
        skill_gap = "run-resume-recovery"
        root_cause = "The worker or server stopped before the run emitted a terminal result."
        recommended_fix = "Persist progress checkpoints and provide a resume or cleanup path for interrupted runs."
        skill_seed = "Create a recovery skill that reconstructs interrupted work from the latest artifacts and events."
    elif "timeout" in lowered:
        failure_stage = "execute"
        failure_type = "timeout"
        skill_gap = "long-running-task-chunking"
        root_cause = "The executor did not finish within the allotted window."
        recommended_fix = "Split the task into smaller milestones or increase timeout only when evidence supports it."
        skill_seed = "Create a chunking skill that decomposes long tasks before execution."
    elif "non-zero exit" in lowered or (code and code.startswith("exit:")):
        failure_stage = "execute"
        failure_type = "tool_error"
        skill_gap = "command-hardening"
        root_cause = "The external tool invocation failed before a reviewable result was produced."
        recommended_fix = "Capture command stderr, validate prerequisites, and add retry logic only for safe transient failures."
        skill_seed = "Create a command hardening skill that validates preconditions and captures actionable stderr."
    elif "missing" in lowered or "requirement" in lowered or "review" in lowered:
        failure_stage = "eval"
        failure_type = "missing_requirement"
        skill_gap = "acceptance-criteria-enforcement"
        root_cause = "The run produced output, but the evaluator found unmet requirements."
        recommended_fix = "Inject the acceptance criteria as an execution checklist and verify them before completion."
        skill_seed = "Create an AC checklist skill that validates deliverables before completion is emitted."
    elif status == "cancelled":
        failure_stage = "approval"
        failure_type = "cancelled"
        skill_gap = "human-in-the-loop-handoff"
        root_cause = "The run was stopped before it reached a reviewable terminal state."
        recommended_fix = "Capture the partial state and require a restart note so the next run resumes with context."
        skill_seed = "Create a cancellation handoff skill that summarizes partial progress before termination."

    return {
        "failureStage": failure_stage,
        "failureType": failure_type,
        "failureReason": trim_text(summary or "Failure reason unavailable.", limit=240),
        "evidence": summarize_evidence(run),
        "rootCauseHypothesis": root_cause,
        "recommendedFix": recommended_fix,
        "skillGap": skill_gap,
        "skillSeed": skill_seed,
        "updatedAt": local_now_iso(),
    }


def parse_markdown_checklist(text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("- [") or len(line) < 6:
            continue
        marker = line[3:4].lower()
        if marker not in {" ", "x"}:
            continue
        label = line[6:].strip()
        if not label:
            continue
        items.append(
            {
                "id": new_id("check"),
                "label": label,
                "done": marker == "x",
                "updatedAt": local_now_iso(),
            }
        )
    return items


def install_lifecycle_signal_handlers() -> None:
    if lifecycle.signal_handlers_installed:
        return

    def make_handler(signum: int, previous_handler: Any):
        signame = signal.Signals(signum).name

        def _handler(*args: Any) -> None:
            lifecycle.mark_shutdown("signal", signame=signame, exit_code=128 + signum)
            if callable(previous_handler):
                previous_handler(*args)
            elif previous_handler == signal.SIG_DFL:
                raise SystemExit(128 + signum)

        return _handler

    for signame in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT"):
        if not hasattr(signal, signame):
            continue
        signum = getattr(signal, signame)
        previous_handler = signal.getsignal(signum)
        signal.signal(signum, make_handler(signum, previous_handler))

    def _excepthook(exc_type: type[BaseException], exc: BaseException, tb: Any) -> None:
        lifecycle.mark_shutdown("uncaught_exception")
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    def _atexit() -> None:
        if lifecycle.snapshot()["reason"] == "unknown":
            lifecycle.mark_shutdown("process_exit", exit_code=0)

    atexit.register(_atexit)
    lifecycle.signal_handlers_installed = True


class RunEventBroadcaster:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.subscribers: list[queue.Queue[str]] = []

    def subscribe(self) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue()
        with self.lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[str]) -> None:
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def publish(self, payload: dict[str, Any]) -> None:
        message = f"data: {json.dumps(payload, ensure_ascii=True)}\n\n"
        with self.lock:
            subscribers = list(self.subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(message)
            except queue.Full:
                continue


class RunJsonlLogger:
    def __init__(self, base_dir: Path, *, max_files: int) -> None:
        self.base_dir = base_dir
        self.max_files = max_files
        self.lock = threading.Lock()

    def create_run_log(self, task_id: str, run_id: str) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        timestamp = local_now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp}_{run_id}.jsonl"
        path = self.base_dir / filename
        path.touch(exist_ok=True)
        self.prune()
        return path

    def append(self, path: str | None, record: dict[str, Any]) -> None:
        if not path:
            return
        log_path = Path(path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=True) + "\n"
        with self.lock:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    def prune(self) -> None:
        files = sorted(self.base_dir.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
        for stale in files[self.max_files :]:
            stale.unlink(missing_ok=True)

    def list_recent(self) -> list[dict[str, Any]]:
        files = sorted(self.base_dir.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)[: self.max_files]
        return [
            {
                "name": item.name,
                "path": str(item),
                "size": item.stat().st_size,
                "modifiedAt": datetime.fromtimestamp(item.stat().st_mtime).astimezone().isoformat(),
            }
            for item in files
        ]

    def read_last_record(self, path: Path) -> dict[str, Any] | None:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return None
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return None

    def reconcile_orphaned_runs(self) -> list[str]:
        terminal_kinds = {"run_failed", "run_action", "process_exit", "completion_result", "orphaned_run"}
        reconciled: list[str] = []
        for metadata in self.list_recent():
            path = Path(metadata["path"])
            last_record = self.read_last_record(path)
            if not last_record:
                continue
            if last_record.get("runStatus") not in {"running", "revising"}:
                continue
            if last_record.get("kind") in terminal_kinds:
                continue
            orphan_record = {
                "ts": local_now_iso(),
                "kind": "orphaned_run",
                "taskId": last_record.get("taskId"),
                "runId": last_record.get("runId"),
                "message": "Run was still active when the server restarted or the worker stopped unexpectedly.",
                "payload": {"previousKind": last_record.get("kind")},
                "runStatus": "orphaned",
                "currentPhase": last_record.get("currentPhase"),
                "summary": last_record.get("summary"),
            }
            self.append(str(path), orphan_record)
            reconciled.append(path.name)
        return reconciled


class SystemJsonlLogger:
    def __init__(self, base_dir: Path, *, max_files: int) -> None:
        self.base_dir = base_dir
        self.max_files = max_files
        self.lock = threading.Lock()

    def current_log_path(self) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / f"{local_now().strftime('%Y-%m-%d')}_server.jsonl"
        path.touch(exist_ok=True)
        self.prune()
        return path

    def append(self, kind: str, message: str, *, payload: dict[str, Any] | None = None) -> None:
        line = json.dumps(
            {
                "ts": local_now_iso(),
                "kind": kind,
                "message": message,
                "payload": payload,
            },
            ensure_ascii=True,
        ) + "\n"
        path = self.current_log_path()
        with self.lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    def prune(self) -> None:
        files = sorted(self.base_dir.glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
        for stale in files[self.max_files :]:
            stale.unlink(missing_ok=True)


class TaskCreate(BaseModel):
    title: str
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
    def __init__(self, *, state_path: Path) -> None:
        self.lock = threading.RLock()
        self.state_path = state_path
        self.tasks: list[dict[str, Any]] = []
        self.runs_by_task_id: dict[str, list[dict[str, Any]]] = {}
        self.publisher: RunEventBroadcaster | None = None
        self.logger: RunJsonlLogger | None = None
        self._seed()

    def _seed(self) -> None:
        self.tasks = []
        self.runs_by_task_id = {}

    def load_state(self) -> None:
        with self.lock:
            if not self.state_path.exists():
                self._seed()
                return
            try:
                payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._seed()
                return
            tasks = payload.get("tasks")
            runs_by_task_id = payload.get("runsByTaskId")
            if not isinstance(tasks, list) or not isinstance(runs_by_task_id, dict):
                self._seed()
                return
            self.tasks = tasks
            self.runs_by_task_id = {
                task_id: runs if isinstance(runs, list) else []
                for task_id, runs in runs_by_task_id.items()
            }

    def save_state(self) -> None:
        with self.lock:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "savedAt": local_now_iso(),
                "tasks": self.tasks,
                "runsByTaskId": self.runs_by_task_id,
            }
            self.state_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def reconcile_in_memory_runs_after_restart(self) -> list[str]:
        reconciled: list[str] = []
        with self.lock:
            for task in self.tasks:
                runs = self.runs_by_task_id.get(task["id"], [])
                for run in runs:
                    if run.get("status") not in {"running", "revising"}:
                        continue
                    run["status"] = "orphaned"
                    run["endedAt"] = local_now_iso()
                    run["currentPhase"] = "eval"
                    run["primaryAgentRole"] = "Evaluator"
                    run["summary"] = "Run was interrupted before completion and needs review or retry."
                    run["verdict"] = {
                        "decision": "retry",
                        "reason": "The server restarted or the worker stopped before completion.",
                        "risks": ["Execution stopped mid-stream and may have partial artifacts only"],
                        "recommendedNextAction": "retry_or_reopen",
                    }
                    run.setdefault("runner", {})["recoveryReason"] = lifecycle.snapshot()["reason"]
                    run["failureAnalysis"] = infer_failure_analysis(run, reason=run["verdict"]["reason"])
                    if len(run.get("steps", [])) > 1:
                        run["steps"][1]["status"] = "failed"
                    if len(run.get("steps", [])) > 2:
                        run["steps"][2]["status"] = "completed"
                        run["steps"][2]["summary"] = "Run marked orphaned during server recovery."
                    self.append_event(
                        run,
                        "orphaned_run",
                        "Run was interrupted while the server restarted or the worker exited.",
                        raw={"recoveryReason": lifecycle.snapshot()["reason"], "shutdownSignal": lifecycle.snapshot()["signal"]},
                    )
                    self.log_executor_lifecycle(
                        run,
                        "run_recovered_orphaned",
                        message="Recovered run as orphaned during startup.",
                        payload={"recoveryReason": lifecycle.snapshot()["reason"], "shutdownSignal": lifecycle.snapshot()["signal"]},
                    )
                    task["latestRunStatus"] = run["status"]
                    reconciled.append(run["id"])
            if reconciled:
                self.save_state()

    def _step(self, phase: str, agent_role: str, status: str, summary: str) -> dict[str, Any]:
        return {
            "id": new_id("step"),
            "phase": phase,
            "agentRole": agent_role,
            "status": status,
            "summary": summary,
        }

    def _event(self, event_type: str, summary: str, *, raw: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "id": new_id("event"),
            "ts": local_now_iso(),
            "type": event_type,
            "summary": summary,
            "raw": sanitize_event_raw(raw),
        }

    def _artifact(self, artifact_type: str, title: str, path: str, *, selected: bool = False, content: str | None = None) -> dict[str, Any]:
        return {
            "id": new_id("artifact"),
            "type": artifact_type,
            "title": title,
            "path": path,
            "selected": selected,
            "content": content,
            "createdAt": local_now_iso(),
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
            now = local_now_iso()
            log_path = self.create_log_path(task_id, run_id)
            task = {
                "id": task_id,
                "title": payload.title.strip(),
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
                "runner": {
                    "provider": "cline" if CLINE_PATH else "mock",
                    "available": bool(CLINE_PATH),
                    "commandPreview": None,
                    "logPath": log_path,
                },
                "events": [self._event("created", "Task and initial draft run were created.")],
                "steps": [self._step("plan", "Planner", "pending", "Planning has not started yet.")],
                "artifacts": [self._artifact("log", "Run JSONL log", log_path or "", selected=False)] if log_path else [],
                "planChecklist": [],
                "verdict": {
                    "decision": "queued",
                    "reason": "No execution has started yet.",
                    "risks": ["Context may still be incomplete"],
                    "recommendedNextAction": "start_run",
                },
                "failureAnalysis": None,
            }
            self.tasks.insert(0, task)
            self.runs_by_task_id[task_id] = [run]
            created_task = deepcopy(task)
            self.save_state()
        self.log_run_record(task_id, run_id, "run_created", message="Task and initial draft run created.")
        self.publish_run_update(task_id, run_id)
        return created_task

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

    def append_event(self, run: dict[str, Any], event_type: str, summary: str, *, raw: dict[str, Any] | None = None) -> None:
        run.setdefault("events", []).append(self._event(event_type, summary, raw=raw))
        run["events"] = run["events"][-40:]
        self.save_state()
        self.log_run_record(
            run["taskId"],
            run["id"],
            "event",
            message=summary,
            payload={"type": event_type, "raw": raw},
        )

    def upsert_artifact(
        self,
        run: dict[str, Any],
        artifact_type: str,
        title: str,
        *,
        content: str,
        path: str = "",
        selected: bool = False,
    ) -> None:
        existing = next((item for item in run["artifacts"] if item["type"] == artifact_type and item["title"] == title), None)
        if existing:
            existing["content"] = content
            existing["path"] = path
            existing["selected"] = selected
            existing["createdAt"] = local_now_iso()
            self.save_state()
            self.log_run_record(
                run["taskId"],
                run["id"],
                "artifact_updated",
                message=f"Updated artifact: {title}",
                payload={"artifactType": artifact_type, "title": title, "path": path, "selected": selected},
            )
            return
        run["artifacts"].append(self._artifact(artifact_type, title, path, selected=selected, content=content))
        self.save_state()
        self.log_run_record(
            run["taskId"],
            run["id"],
            "artifact_created",
            message=f"Created artifact: {title}",
            payload={"artifactType": artifact_type, "title": title, "path": path, "selected": selected},
        )

    def set_publisher(self, publisher: RunEventBroadcaster) -> None:
        self.publisher = publisher

    def set_logger(self, logger: RunJsonlLogger) -> None:
        self.logger = logger

    def create_log_path(self, task_id: str, run_id: str) -> str | None:
        if not self.logger:
            return None
        return str(self.logger.create_run_log(task_id, run_id))

    def log_run_record(
        self,
        task_id: str,
        run_id: str,
        kind: str,
        *,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if not self.logger:
            return
        run = self.get_run(run_id)
        log_path = run.get("runner", {}).get("logPath") if run else None
        record = {
            "ts": local_now_iso(),
            "kind": kind,
            "taskId": task_id,
            "runId": run_id,
            "message": message,
            "payload": sanitize_event_raw(payload) if payload else None,
            "runStatus": run.get("status") if run else None,
            "currentPhase": run.get("currentPhase") if run else None,
            "summary": run.get("summary") if run else None,
        }
        self.logger.append(log_path, record)

    def log_executor_lifecycle(
        self,
        run: dict[str, Any],
        kind: str,
        *,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.log_run_record(run["taskId"], run["id"], kind, message=message, payload=payload)
        system_logger.append(
            kind,
            message,
            payload={
                "taskId": run["taskId"],
                "runId": run["id"],
                "runStatus": run.get("status"),
                "runner": run.get("runner"),
                **(payload or {}),
            },
        )

    def build_run_payload(self, task: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
        return {
            "task": {**deepcopy(task), "latestRun": self.run_snapshot(run)},
            "run": deepcopy(run),
            "artifacts": deepcopy(run["artifacts"]),
            "planChecklist": deepcopy(run.get("planChecklist", [])),
            "verdict": deepcopy(run["verdict"]),
            "failureAnalysis": deepcopy(run.get("failureAnalysis")),
        }

    def publish_run_update(self, task_id: str, run_id: str) -> None:
        if not self.publisher:
            self.log_run_record(task_id, run_id, "run_update", message="Run update prepared without active subscribers.")
            return
        task = self.get_task(task_id)
        run = self.get_run_or_404(run_id)
        self.log_run_record(task_id, run_id, "run_update", message="Published run update to stream subscribers.")
        self.publisher.publish(
            {
                "kind": "run_update",
                "taskId": task_id,
                "runId": run_id,
                "payload": self.build_run_payload(task, run),
            }
        )

    def create_run(self, task_id: str, payload: RunCreate) -> dict[str, Any]:
        with self.lock:
            task = self.get_task(task_id)
            previous_run = self.get_run_or_404(task["latestRunId"])
            run_id = new_id("run")
            log_path = self.create_log_path(task_id, run_id)
            command_preview = build_cline_command_preview(task, previous_run["mode"])
            status = "running" if payload.action == "start" else "revising"
            run = {
                "id": run_id,
                "taskId": task_id,
                "mode": previous_run["mode"],
                "status": status,
                "startedAt": local_now_iso(),
                "endedAt": None,
                "currentPhase": "execute",
                "primaryAgentRole": "Cline Executor" if payload.useCline and CLINE_PATH else "Executor",
                "summary": "Cline executor is preparing the next attempt." if payload.useCline and CLINE_PATH else "Execution restarted without a live Cline invocation.",
                "runner": {
                    "provider": "cline" if payload.useCline and CLINE_PATH else "mock",
                    "available": bool(CLINE_PATH),
                    "commandPreview": command_preview,
                    "logPath": log_path,
                },
                "events": [
                    self._event(
                        "run_started",
                        "Run created and queued for execution via Cline." if payload.useCline and CLINE_PATH else "Run created without a live Cline executor.",
                    )
                ],
                "steps": [
                    self._step("plan", "Planner", "completed", "Reframed the goal and constraints for the next run."),
                    self._step("execute", "Cline Executor" if payload.useCline and CLINE_PATH else "Executor", "running", "Execution is in progress."),
                    self._step("eval", "Evaluator", "pending", "Waiting for artifacts from the new run."),
                ],
                "artifacts": [self._artifact("log", "Run JSONL log", log_path or "", selected=False)] if log_path else [],
                "planChecklist": [],
                "verdict": {
                    "decision": "pending",
                    "reason": "The run is still in progress.",
                    "risks": ["Fresh evidence has not been reviewed yet"],
                    "recommendedNextAction": "continue_run",
                },
                "failureAnalysis": None,
            }
            self.runs_by_task_id.setdefault(task_id, []).insert(0, run)
            task["latestRunId"] = run_id
            task["latestRunStatus"] = status
            self.save_state()
        self.log_run_record(task_id, run_id, "run_created", message=f"Run created via action={payload.action}.")
        if payload.useCline and CLINE_PATH:
            self.start_cline_run(task_id, run_id)
        self.publish_run_update(task_id, run_id)
        return deepcopy(run)

    def patch_run(self, run_id: str, payload: RunAction) -> dict[str, Any]:
        with self.lock:
            run = self.get_run_or_404(run_id)
            task = self.get_task(run["taskId"])
            if payload.action == "approve":
                run["status"] = "completed"
                run["endedAt"] = local_now_iso()
                run["currentPhase"] = "eval"
                run["primaryAgentRole"] = "Evaluator"
                run["summary"] = "Run approved from the workbench."
                run["verdict"] = {
                    "decision": "approved",
                    "reason": "The current result was approved by the user.",
                    "risks": ["Manual approval does not guarantee downstream merge readiness"],
                    "recommendedNextAction": "approved",
                }
                run["failureAnalysis"] = None
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
                run["failureAnalysis"] = None
                run["steps"] = [self._step("plan", "Planner", "pending", "Planning will resume when the task is started again.")]
            else:
                run["status"] = "cancelled"
                run["endedAt"] = local_now_iso()
                run["currentPhase"] = "eval"
                run["primaryAgentRole"] = "Evaluator"
                run["summary"] = "Run was cancelled from the workbench."
                run["verdict"] = {
                    "decision": "cancelled",
                    "reason": "The user stopped the run before completion.",
                    "risks": ["Partial artifacts may not be actionable"],
                    "recommendedNextAction": "retry",
                }
                run["failureAnalysis"] = infer_failure_analysis(run)
            task["latestRunId"] = run["id"]
            task["latestRunStatus"] = run["status"]
            patched_run = deepcopy(run)
            self.save_state()
        self.log_run_record(
            patched_run["taskId"],
            patched_run["id"],
            "run_action",
            message=f"Applied run action: {payload.action}",
            payload={"action": payload.action, "status": patched_run["status"]},
        )
        self.publish_run_update(patched_run["taskId"], patched_run["id"])
        return patched_run

    def delete_task(self, task_id: str) -> None:
        with self.lock:
            task = self.get_task(task_id)
            self.tasks = [item for item in self.tasks if item["id"] != task_id]
            removed_runs = self.runs_by_task_id.pop(task_id, [])
            self.save_state()
        self.log_run_record(
            task_id,
            task.get("latestRunId") or "deleted",
            "task_deleted",
            message=f"Deleted task {task_id}.",
            payload={"runCount": len(removed_runs)},
        )

    def start_cline_run(self, task_id: str, run_id: str) -> None:
        thread = threading.Thread(target=self._execute_cline_run, args=(task_id, run_id), daemon=True)
        thread.start()

    def _update_run_from_cline_event(self, task_id: str, run_id: str, event: dict[str, Any]) -> None:
        run = self.get_run_or_404(run_id)
        event_type = event.get("type", "unknown")
        say_type = event.get("say")
        text = event.get("text") or ""
        task = self.get_task(task_id)

        if event_type == "task_started":
            run["summary"] = "Cline task session started."
            run["currentPhase"] = "execute"
            run["primaryAgentRole"] = "Cline Executor"
            self.append_event(run, "task_started", "Cline accepted the task and started a session.", raw=event)
            task["latestRunStatus"] = run["status"]
            return

        if event_type == "say" and say_type == "api_req_started":
            run["summary"] = "Cline sent a model request."
            self.append_event(run, "model_request", "Model request started.", raw=event)
            return

        if event_type == "say" and say_type == "reasoning":
            summary = trim_text(text or "Reasoning update received.")
            run["summary"] = summary
            run["steps"][1]["summary"] = summary
            self.append_event(run, "reasoning", summary, raw=event)
            self.upsert_artifact(run, "reasoning", "Cline reasoning trace", content=text)
            return

        if event_type == "say" and say_type == "text":
            summary = trim_text(text or "Text output received.")
            run["summary"] = summary
            run["steps"][1]["summary"] = summary
            self.append_event(run, "assistant_text", summary, raw=event)
            self.upsert_artifact(run, "transcript", "Cline live transcript", content=text)
            return

        if event_type == "say" and say_type == "task_progress":
            checklist = parse_markdown_checklist(text)
            if checklist:
                run["planChecklist"] = checklist
            self.append_event(run, "task_progress", trim_text(text or "Task progress updated."), raw=event)
            self.upsert_artifact(run, "task_progress", "Cline task progress", content=text)
            return

        if event_type == "say" and say_type == "tool":
            payload = parse_tool_payload(text)
            summary, artifact_type = summarize_tool_payload(payload, text)
            run["steps"][1]["summary"] = summary
            self.append_event(run, "tool", summary, raw={**event, "toolPayload": payload} if payload else event)
            self.upsert_artifact(run, artifact_type, f"Cline {artifact_type.replace('_', ' ')}", content=text)
            return

        if event_type == "say" and say_type == "task":
            self.append_event(run, "task_prompt", trim_text(text or "Task prompt emitted."), raw=event)
            return

        if event_type == "say" and say_type == "completion_result":
            summary = trim_text(text or "Completion result received.")
            run["status"] = "awaiting_review"
            run["endedAt"] = local_now_iso()
            run["currentPhase"] = "eval"
            run["primaryAgentRole"] = "Evaluator"
            run["summary"] = "Cline completed execution. Review is required before approval."
            run["verdict"] = {
                "decision": "review_required",
                "reason": summary,
                "risks": ["CLI output may still need manual validation"],
                "recommendedNextAction": "approve_or_retry",
            }
            run["failureAnalysis"] = None
            run["steps"][1]["status"] = "completed"
            run["steps"][1]["summary"] = summary
            run["steps"][2]["status"] = "completed"
            run["steps"][2]["summary"] = "Cline returned a completion result and is ready for review."
            self.append_event(run, "completion_result", summary, raw=event)
            self.upsert_artifact(run, "result", "Cline completion result", content=text, selected=True)
            task["latestRunStatus"] = run["status"]
            return

        self.append_event(run, event_type, trim_text(text or f"Unhandled Cline event: {event_type}"), raw=event)

    def _execute_cline_run(self, task_id: str, run_id: str) -> None:
        try:
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
                self.append_event(run, "command_preview", "Cline command prepared.")
                self.upsert_artifact(run, "command", "Cline command preview", content=" ".join(command))
            self.publish_run_update(task_id, run_id)
            try:
                process = subprocess.Popen(
                    command,
                    cwd=BASE_DIR,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            except OSError as exc:
                with self.lock:
                    self._mark_run_failed(run_id, f"Cline failed to start: {exc}", "spawn")
                self.publish_run_update(task_id, run_id)
                return
            with self.lock:
                current_run = self.get_run_or_404(run_id)
                current_run["runner"]["processId"] = process.pid
                current_run["runner"]["spawnedAt"] = local_now_iso()
                current_run["runner"]["lastKnownState"] = "running"
                self.save_state()
                self.log_executor_lifecycle(
                    current_run,
                    "executor_spawned",
                    message="Started Cline subprocess for run execution.",
                    payload={"processId": process.pid, "command": command},
                )
            stdout_lines: list[str] = []
            try:
                assert process.stdout is not None
                for line in process.stdout:
                    raw_line = line.strip()
                    if not raw_line:
                        continue
                    stdout_lines.append(raw_line)
                    try:
                        event = json.loads(raw_line)
                    except json.JSONDecodeError:
                        with self.lock:
                            current_run = self.get_run_or_404(run_id)
                            self.append_event(current_run, "stdout", trim_text(raw_line), raw={"line": raw_line})
                            self.upsert_artifact(current_run, "stdout", "Cline raw stdout", content="\n".join(stdout_lines))
                        self.publish_run_update(task_id, run_id)
                        continue
                    with self.lock:
                        current_run = self.get_run_or_404(run_id)
                        self._update_run_from_cline_event(task_id, run_id, event)
                        self.upsert_artifact(current_run, "event_stream", "Cline JSON event stream", content="\n".join(stdout_lines))
                    self.publish_run_update(task_id, run_id)
                return_code = process.wait(timeout=CLINE_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                with self.lock:
                    current_run = self.get_run_or_404(run_id)
                    current_run["runner"]["lastKnownState"] = "killed"
                    current_run["runner"]["terminatedAt"] = local_now_iso()
                    current_run["runner"]["terminationReason"] = "timeout"
                    self.log_executor_lifecycle(
                        current_run,
                        "executor_killed",
                        message="Killed Cline subprocess after timeout.",
                        payload={"processId": current_run["runner"].get("processId"), "reason": "timeout"},
                    )
                    self._mark_run_failed(run_id, "Cline timed out before producing a reviewable result.", "timeout")
                self.publish_run_update(task_id, run_id)
                return

            with self.lock:
                current_run = self.get_run_or_404(run_id)
                current_run["runner"]["lastKnownState"] = "exited"
                current_run["runner"]["terminatedAt"] = local_now_iso()
                current_run["runner"]["exitCode"] = return_code
                self.log_executor_lifecycle(
                    current_run,
                    "executor_exited",
                    message="Cline subprocess exited.",
                    payload={"processId": current_run["runner"].get("processId"), "exitCode": return_code},
                )
                self.upsert_artifact(current_run, "event_stream", "Cline JSON event stream", content="\n".join(stdout_lines))
                if return_code != 0:
                    self._mark_run_failed(run_id, "Cline returned a non-zero exit code.", f"exit:{return_code}")
                    self.upsert_artifact(current_run, "log", "Cline session output", content="\n".join(stdout_lines), selected=False)
                elif current_run["status"] not in {"awaiting_review", "completed"}:
                    summary = "Cline process exited without a completion_result event."
                    current_run["status"] = "awaiting_review"
                    current_run["endedAt"] = local_now_iso()
                    current_run["currentPhase"] = "eval"
                    current_run["primaryAgentRole"] = "Evaluator"
                    current_run["summary"] = summary
                    current_run["verdict"] = {
                        "decision": "review_required",
                        "reason": summary,
                        "risks": ["Completion semantics were inferred from process exit"],
                        "recommendedNextAction": "approve_or_retry",
                    }
                    current_run["failureAnalysis"] = infer_failure_analysis(current_run, reason=summary)
                    current_run["steps"][1]["status"] = "completed"
                    current_run["steps"][2]["status"] = "completed"
                    current_run["steps"][2]["summary"] = "Process exited cleanly without an explicit completion event."
                    self.append_event(current_run, "process_exit", summary, raw={"returnCode": return_code})
                    task = self.get_task(task_id)
                    task["latestRunStatus"] = current_run["status"]
            self.publish_run_update(task_id, run_id)
        except Exception as exc:
            with self.lock:
                self._mark_run_failed(run_id, f"Unhandled executor exception: {exc}", "exception")
            self.publish_run_update(task_id, run_id)

    def _mark_run_failed(self, run_id: str, reason: str, code: str) -> None:
        run = self.get_run_or_404(run_id)
        run["status"] = "failed"
        run["endedAt"] = local_now_iso()
        run["currentPhase"] = "eval"
        run["primaryAgentRole"] = "Evaluator"
        run["summary"] = reason
        run["verdict"] = {
            "decision": "retry",
            "reason": f"{reason} ({code})",
            "risks": ["No accepted artifact was produced"],
            "recommendedNextAction": "retry",
        }
        run["failureAnalysis"] = infer_failure_analysis(run, code=code, reason=reason)
        if len(run["steps"]) > 1:
            run["steps"][1]["status"] = "failed"
            run["steps"][1]["summary"] = reason
        if len(run["steps"]) > 2:
            run["steps"][2]["status"] = "completed"
            run["steps"][2]["summary"] = "Evaluator marked the run as failed."
        task = self.get_task(run["taskId"])
        task["latestRunStatus"] = "failed"
        self.append_event(run, "failure", reason, raw={"code": code})
        self.log_run_record(run["taskId"], run["id"], "run_failed", message=reason, payload={"code": code})


def build_cline_prompt(task: dict[str, Any], run: dict[str, Any]) -> str:
    constraints = "\n".join(f"- {item}" for item in task["constraints"]) or "- None provided"
    paths = "\n".join(f"- {item}" for item in task.get("relatedPaths", [])) or "- None provided"
    return (
        "You are operating inside the KanbanWithCline workbench.\n"
        f"Task title: {task['title']}\n"
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


broadcaster = RunEventBroadcaster()
run_logger = RunJsonlLogger(RUN_LOG_DIR, max_files=MAX_RUN_LOG_FILES)
system_logger = SystemJsonlLogger(SYSTEM_LOG_DIR, max_files=MAX_RUN_LOG_FILES)
store = InMemoryStore(state_path=STATE_PATH)
store.set_publisher(broadcaster)
store.set_logger(run_logger)
app = FastAPI()


@app.on_event("startup")
def on_startup() -> None:
    startup_snapshot = lifecycle.snapshot()
    store.load_state()
    recovered_runs = store.reconcile_in_memory_runs_after_restart()
    reconciled = run_logger.reconcile_orphaned_runs()
    system_logger.append(
        "server_start",
        "Workbench server started.",
        payload={
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "startupReason": startup_snapshot["reason"],
            "startupSignal": startup_snapshot["signal"],
            "reconciledOrphanedLogs": reconciled,
            "recoveredRuns": recovered_runs,
            "runLogDir": str(RUN_LOG_DIR),
            "statePath": str(STATE_PATH),
        },
    )


@app.on_event("shutdown")
def on_shutdown() -> None:
    shutdown_snapshot = lifecycle.snapshot()
    shutdown_reason = shutdown_snapshot["reason"]
    if shutdown_reason in {"unknown", "process_start"}:
        shutdown_reason = "application_shutdown"
    active_runs = [
        {"taskId": task_id, "runId": run["id"], "status": run["status"]}
        for task_id, runs in store.runs_by_task_id.items()
        for run in runs
        if run["status"] in {"running", "revising"}
    ]
    system_logger.append(
        "server_shutdown",
        "Workbench server stopped.",
        payload={
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "shutdownReason": shutdown_reason,
            "shutdownSignal": shutdown_snapshot["signal"],
            "exitCode": shutdown_snapshot["exitCode"],
            "activeRuns": active_runs,
        },
    )


@app.get("/api/meta")
def get_meta() -> dict[str, Any]:
    return {
        "clineAvailable": bool(CLINE_PATH),
        "clinePath": CLINE_PATH,
        "timeoutSeconds": CLINE_TIMEOUT_SECONDS,
        "statusGroups": {key: sorted(value) for key, value in RUN_STATUS_GROUPS.items()},
        "streaming": {"sse": True},
        "runLogs": {"dir": str(RUN_LOG_DIR), "maxFiles": MAX_RUN_LOG_FILES},
        "state": {"path": str(STATE_PATH)},
    }


@app.get("/api/run-logs")
def list_run_logs() -> list[dict[str, Any]]:
    return run_logger.list_recent()


@app.get("/api/stream")
def stream_run_updates() -> StreamingResponse:
    subscriber = broadcaster.subscribe()

    def event_generator():
        yield "event: ready\ndata: {\"kind\":\"ready\"}\n\n"
        try:
            while True:
                try:
                    message = subscriber.get(timeout=15)
                    yield message
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            broadcaster.unsubscribe(subscriber)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/tasks")
def list_tasks() -> list[dict[str, Any]]:
    return store.list_tasks()


@app.post("/api/tasks")
def create_task(payload: TaskCreate) -> dict[str, Any]:
    return store.create_task(payload)


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: str) -> None:
    store.delete_task(task_id)


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
    install_lifecycle_signal_handlers()
    lifecycle.mark_shutdown("process_start")
    local_ip = get_local_ip()
    port = 8000
    print("\n" + "=" * 50)
    print("Kanban Web App is running.")
    print(f"Access URL: http://{local_ip}:{port}")
    print("=" * 50 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
