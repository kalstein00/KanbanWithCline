from __future__ import annotations

import socket
import json
import queue
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
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
RUN_LOG_DIR = BASE_DIR / "logs" / "runs"
CLINE_PATH = which("cline")
CLINE_TIMEOUT_SECONDS = 120
MAX_RUN_LOG_FILES = 5

RUN_STATUS_GROUPS = {
    "queue": {"draft", "planned"},
    "stream": {"running", "awaiting_review", "revising"},
    "synthesis": {"completed", "failed", "cancelled"},
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


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
        filename = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}_{task_id}_{run_id}.jsonl"
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
                "modifiedAt": datetime.fromtimestamp(item.stat().st_mtime, UTC).isoformat(),
            }
            for item in files
        ]


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
        self.publisher: RunEventBroadcaster | None = None
        self.logger: RunJsonlLogger | None = None
        self._seed()

    def _seed(self) -> None:
        self.tasks = []
        self.runs_by_task_id = {}

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
            "ts": utc_now(),
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
            log_path = self.create_log_path(task_id, run_id)
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
                "runner": {
                    "provider": "cline" if CLINE_PATH else "mock",
                    "available": bool(CLINE_PATH),
                    "commandPreview": None,
                    "logPath": log_path,
                },
                "events": [self._event("created", "Task and initial draft run were created.")],
                "steps": [self._step("plan", "Planner", "pending", "Planning has not started yet.")],
                "artifacts": [self._artifact("log", "Run JSONL log", log_path or "", selected=False)] if log_path else [],
                "verdict": {
                    "decision": "queued",
                    "reason": "No execution has started yet.",
                    "risks": ["Context may still be incomplete"],
                    "recommendedNextAction": "start_run",
                },
            }
            self.tasks.insert(0, task)
            self.runs_by_task_id[task_id] = [run]
            created_task = deepcopy(task)
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
            existing["createdAt"] = utc_now()
            self.log_run_record(
                run["taskId"],
                run["id"],
                "artifact_updated",
                message=f"Updated artifact: {title}",
                payload={"artifactType": artifact_type, "title": title, "path": path, "selected": selected},
            )
            return
        run["artifacts"].append(self._artifact(artifact_type, title, path, selected=selected, content=content))
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
            "ts": utc_now(),
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

    def build_run_payload(self, task: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
        return {
            "task": {**deepcopy(task), "latestRun": self.run_snapshot(run)},
            "run": deepcopy(run),
            "artifacts": deepcopy(run["artifacts"]),
            "verdict": deepcopy(run["verdict"]),
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
                "startedAt": utc_now(),
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
            patched_run = deepcopy(run)
        self.log_run_record(
            patched_run["taskId"],
            patched_run["id"],
            "run_action",
            message=f"Applied run action: {payload.action}",
            payload={"action": payload.action, "status": patched_run["status"]},
        )
        self.publish_run_update(patched_run["taskId"], patched_run["id"])
        return patched_run

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
            run["endedAt"] = utc_now()
            run["currentPhase"] = "eval"
            run["primaryAgentRole"] = "Evaluator"
            run["summary"] = "Cline completed execution. Review is required before approval."
            run["verdict"] = {
                "decision": "review_required",
                "reason": summary,
                "risks": ["CLI output may still need manual validation"],
                "recommendedNextAction": "approve_or_retry",
            }
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
            return
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
                self._mark_run_failed(run_id, "Cline timed out before producing a reviewable result.", "timeout")
            self.publish_run_update(task_id, run_id)
            return

        with self.lock:
            current_run = self.get_run_or_404(run_id)
            self.upsert_artifact(current_run, "event_stream", "Cline JSON event stream", content="\n".join(stdout_lines))
            if return_code != 0:
                self._mark_run_failed(run_id, "Cline returned a non-zero exit code.", f"exit:{return_code}")
                self.upsert_artifact(current_run, "log", "Cline session output", content="\n".join(stdout_lines), selected=False)
            elif current_run["status"] not in {"awaiting_review", "completed"}:
                summary = "Cline process exited without a completion_result event."
                current_run["status"] = "awaiting_review"
                current_run["endedAt"] = utc_now()
                current_run["currentPhase"] = "eval"
                current_run["primaryAgentRole"] = "Evaluator"
                current_run["summary"] = summary
                current_run["verdict"] = {
                    "decision": "review_required",
                    "reason": summary,
                    "risks": ["Completion semantics were inferred from process exit"],
                    "recommendedNextAction": "approve_or_retry",
                }
                current_run["steps"][1]["status"] = "completed"
                current_run["steps"][2]["status"] = "completed"
                current_run["steps"][2]["summary"] = "Process exited cleanly without an explicit completion event."
                self.append_event(current_run, "process_exit", summary, raw={"returnCode": return_code})
                task = self.get_task(task_id)
                task["latestRunStatus"] = current_run["status"]
        self.publish_run_update(task_id, run_id)

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
        self.append_event(run, "failure", reason, raw={"code": code})
        self.log_run_record(run["taskId"], run["id"], "run_failed", message=reason, payload={"code": code})


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


broadcaster = RunEventBroadcaster()
run_logger = RunJsonlLogger(RUN_LOG_DIR, max_files=MAX_RUN_LOG_FILES)
store = InMemoryStore()
store.set_publisher(broadcaster)
store.set_logger(run_logger)
app = FastAPI()


@app.get("/api/meta")
def get_meta() -> dict[str, Any]:
    return {
        "clineAvailable": bool(CLINE_PATH),
        "clinePath": CLINE_PATH,
        "timeoutSeconds": CLINE_TIMEOUT_SECONDS,
        "statusGroups": {key: sorted(value) for key, value in RUN_STATUS_GROUPS.items()},
        "streaming": {"sse": True},
        "runLogs": {"dir": str(RUN_LOG_DIR), "maxFiles": MAX_RUN_LOG_FILES},
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
