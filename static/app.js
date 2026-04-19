const BOARD_GROUPS = {
    queue: ["draft", "planned"],
    stream: ["running", "awaiting_review", "revising"],
    synthesis: ["completed", "failed", "cancelled", "orphaned"],
};

const MODE_LABELS = {
    "plan-execute-eval": "Planner -> Executor -> Evaluator",
    "single-agent": "Single Agent",
    debate: "Debate",
};

const ARTIFACT_SCROLL_LINE_THRESHOLD = 12;
const ARTIFACT_SCROLL_CHAR_THRESHOLD = 1200;

const state = {
    meta: {
        clineAvailable: false,
        clinePath: null,
        timeoutSeconds: null,
    },
    tasks: [],
    runsByTaskId: {},
    artifactsByRunId: {},
    verdictsByRunId: {},
    selectedTaskId: null,
    selectedRunIdByTaskId: {},
    stream: {
        connected: false,
        supported: false,
        source: null,
    },
    filters: {
        status: "all",
    },
    ui: {
        loadingBoard: true,
        loadingDetail: false,
        backgroundRefreshing: false,
        actionPending: false,
        error: "",
    },
};

const columns = document.querySelectorAll(".column");
const modal = document.getElementById("taskModal");
const addTaskBtn = document.getElementById("addTaskBtn");
const cancelBtn = document.getElementById("cancelBtn");
const saveBtn = document.getElementById("saveBtn");
const retryBtn = document.getElementById("retryBtn");
const reopenBtn = document.getElementById("reopenBtn");
const approveBtn = document.getElementById("approveBtn");
const cancelRunBtn = document.getElementById("cancelRunBtn");
const deleteTaskBtn = document.getElementById("deleteTaskBtn");
const taskTitleInput = document.getElementById("taskTitleInput");
const taskGoalInput = document.getElementById("taskGoalInput");
const taskConstraintsInput = document.getElementById("taskConstraintsInput");
const taskModeInput = document.getElementById("taskModeInput");
const taskPriorityInput = document.getElementById("taskPriorityInput");
const taskPathsInput = document.getElementById("taskPathsInput");
const statusFilter = document.getElementById("statusFilter");
const globalBanner = document.getElementById("globalBanner");

async function api(path, options = {}) {
    const response = await fetch(path, {
        headers: {
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
        ...options,
    });

    if (!response.ok) {
        let detail = "Request failed";
        try {
            const errorBody = await response.json();
            detail = errorBody.detail || detail;
        } catch {
            detail = response.statusText || detail;
        }
        throw new Error(detail);
    }

    if (response.status === 204) {
        return null;
    }

    return response.json();
}

async function initWorkbench() {
    bindEvents();
    renderWorkbench();
    await loadMeta();
    await loadBoard();
    connectRunStream();
    window.setInterval(pollActiveRuns, 5000);
}

function bindEvents() {
    addTaskBtn.addEventListener("click", openTaskModal);
    cancelBtn.addEventListener("click", closeTaskModal);
    saveBtn.addEventListener("click", createTask);

    statusFilter.addEventListener("change", (event) => {
        state.filters.status = event.target.value;
        renderWorkbench();
    });

    retryBtn.addEventListener("click", () => {
        const run = getSelectedRun();
        const action = getPrimaryRunAction(run?.status);
        triggerRunAction(action);
    });
    reopenBtn.addEventListener("click", () => patchRun("reopen"));
    approveBtn.addEventListener("click", () => patchRun("approve"));
    cancelRunBtn.addEventListener("click", () => patchRun("cancel"));
    deleteTaskBtn.addEventListener("click", deleteSelectedTask);
}

function connectRunStream() {
    if (!window.EventSource || state.stream.source || state.meta.streaming?.sse !== true) {
        return;
    }

    state.stream.supported = true;
    const source = new EventSource("/api/stream");
    state.stream.source = source;

    source.addEventListener("open", () => {
        state.stream.connected = true;
        renderBanner();
    });

    source.addEventListener("message", (event) => {
        try {
            const data = JSON.parse(event.data);
            handleStreamMessage(data);
        } catch (error) {
            state.ui.error = `Stream payload failed to parse: ${error.message}`;
            renderBanner();
        }
    });

    source.addEventListener("error", () => {
        state.stream.connected = false;
        renderBanner();
    });
}

function handleStreamMessage(message) {
    if (message.kind !== "run_update" || !message.payload) {
        return;
    }

    const { task, run, artifacts, verdict } = message.payload;
    if (task) {
        upsertTask(task);
    }
    if (run) {
        replaceRunInCache(run.taskId, run);
        state.artifactsByRunId[run.id] = artifacts || run.artifacts || [];
        state.verdictsByRunId[run.id] = verdict || run.verdict || null;
        state.selectedRunIdByTaskId[run.taskId] = state.selectedRunIdByTaskId[run.taskId] || run.id;
    }
    renderWorkbench();
}

function upsertTask(task) {
    const index = state.tasks.findIndex((item) => item.id === task.id);
    if (index >= 0) {
        state.tasks[index] = task;
    } else {
        state.tasks.unshift(task);
    }
}

async function loadMeta() {
    try {
        state.meta = await api("/api/meta");
    } catch (error) {
        state.ui.error = `Executor metadata failed to load: ${error.message}`;
    } finally {
        renderBanner();
    }
}

async function loadBoard(options = {}) {
    const { background = false } = options;

    if (background) {
        state.ui.backgroundRefreshing = true;
    } else {
        state.ui.loadingBoard = true;
        state.ui.error = "";
        renderWorkbench();
    }

    try {
        state.tasks = await api("/api/tasks");
        syncSelectionAfterBoardLoad();
        if (state.selectedTaskId) {
            await loadTaskDetail(state.selectedTaskId, null, { background });
        }
    } catch (error) {
        state.ui.error = `Task list failed to load: ${error.message}`;
    } finally {
        if (background) {
            state.ui.backgroundRefreshing = false;
        } else {
            state.ui.loadingBoard = false;
        }
        renderWorkbench();
    }
}

function syncSelectionAfterBoardLoad() {
    if (!state.tasks.length) {
        state.selectedTaskId = null;
        return;
    }

    const existing = state.tasks.find((task) => task.id === state.selectedTaskId);
    state.selectedTaskId = existing ? existing.id : state.tasks[0].id;
}

async function loadTaskDetail(taskId, preferredRunId = null, options = {}) {
    const { background = false } = options;

    if (!background) {
        state.ui.loadingDetail = true;
        renderWorkbench();
    }

    try {
        const runs = await api(`/api/tasks/${taskId}/runs`);
        state.runsByTaskId[taskId] = runs;

        const selectedRunId = preferredRunId
            || state.selectedRunIdByTaskId[taskId]
            || runs[0]?.id
            || null;

        state.selectedRunIdByTaskId[taskId] = selectedRunId;
        if (!selectedRunId) {
            return;
        }

        const [run, artifacts, verdict] = await Promise.all([
            api(`/api/runs/${selectedRunId}`),
            api(`/api/runs/${selectedRunId}/artifacts`),
            api(`/api/runs/${selectedRunId}/verdict`),
        ]);

        replaceRunInCache(taskId, run);
        state.artifactsByRunId[selectedRunId] = artifacts;
        state.verdictsByRunId[selectedRunId] = verdict;
    } catch (error) {
        state.ui.error = `Run detail failed to load: ${error.message}`;
    } finally {
        if (!background) {
            state.ui.loadingDetail = false;
        }
        renderWorkbench();
    }
}

function replaceRunInCache(taskId, run) {
    const runs = state.runsByTaskId[taskId] || [];
    const index = runs.findIndex((item) => item.id === run.id);
    if (index >= 0) {
        runs[index] = run;
    } else {
        runs.unshift(run);
    }
}

async function createTask() {
    const title = taskTitleInput.value.trim();
    const goal = taskGoalInput.value.trim();
    const mode = taskModeInput.value;
    const priority = taskPriorityInput.value;
    const constraints = splitMultiline(taskConstraintsInput.value);
    const relatedPaths = splitMultiline(taskPathsInput.value);

    if (!title || !goal) {
        window.alert("Title and goal are required.");
        return;
    }

    state.ui.actionPending = true;
    renderWorkbench();

    try {
        const task = await api("/api/tasks", {
            method: "POST",
            body: JSON.stringify({ title, goal, mode, priority, constraints, relatedPaths }),
        });
        closeTaskModal();
        await loadBoard();
        state.selectedTaskId = task.id;
        await loadTaskDetail(task.id);
    } catch (error) {
        state.ui.error = `Task creation failed: ${error.message}`;
        renderBanner();
    } finally {
        state.ui.actionPending = false;
        renderWorkbench();
    }
}

async function triggerRunAction(action) {
    const task = getSelectedTask();
    if (!task) {
        return;
    }

    state.ui.actionPending = true;
    renderWorkbench();

    try {
        const run = await api(`/api/tasks/${task.id}/runs`, {
            method: "POST",
            body: JSON.stringify({ action, useCline: true }),
        });
        await loadBoard();
        state.selectedTaskId = task.id;
        await loadTaskDetail(task.id, run.id);
        state.ui.error = "";
    } catch (error) {
        state.ui.error = `Run action failed: ${error.message}`;
        renderBanner();
    } finally {
        state.ui.actionPending = false;
        renderWorkbench();
    }
}

async function patchRun(action) {
    const run = getSelectedRun();
    if (!run) {
        return;
    }

    state.ui.actionPending = true;
    renderWorkbench();

    try {
        await api(`/api/runs/${run.id}`, {
            method: "PATCH",
            body: JSON.stringify({ action }),
        });
        await loadBoard();
        await loadTaskDetail(run.taskId, run.id);
        state.ui.error = "";
    } catch (error) {
        state.ui.error = `State transition failed: ${error.message}`;
        renderBanner();
    } finally {
        state.ui.actionPending = false;
        renderWorkbench();
    }
}

async function deleteSelectedTask() {
    const task = getSelectedTask();
    if (!task) {
        return;
    }

    const run = getLatestRun(task);
    if (["running", "revising"].includes(run?.status)) {
        window.alert("Active runs cannot be deleted. Cancel or let them finish first.");
        return;
    }

    const confirmed = window.confirm(`Delete task "${task.title}" and its run history from the board?`);
    if (!confirmed) {
        return;
    }

    state.ui.actionPending = true;
    renderWorkbench();

    try {
        await api(`/api/tasks/${task.id}`, { method: "DELETE" });
        removeTaskFromState(task.id);
        syncSelectionAfterBoardLoad();
        if (state.selectedTaskId) {
            await loadTaskDetail(state.selectedTaskId);
        }
        state.ui.error = "";
    } catch (error) {
        state.ui.error = `Task deletion failed: ${error.message}`;
        renderBanner();
    } finally {
        state.ui.actionPending = false;
        renderWorkbench();
    }
}

async function pollActiveRuns() {
    if (state.stream.connected) {
        return;
    }

    if (state.ui.loadingBoard || state.ui.loadingDetail || state.ui.actionPending || state.ui.backgroundRefreshing) {
        return;
    }

    const activeTask = state.tasks.find((task) =>
        ["running", "revising", "awaiting_review"].includes(task.latestRunStatus)
    );

    if (!activeTask) {
        return;
    }

    await loadBoard({ background: true });
}

function renderWorkbench() {
    renderBanner();
    renderBoard();
    renderSidebarSummary();
    renderDetailPanel();
}

function renderBanner() {
    const notices = [];
    if (state.meta.clineAvailable) {
        notices.push(`Cline connected via ${state.meta.clinePath}`);
    } else {
        notices.push("Cline not detected. Run actions use the mock executor path.");
    }

    if (state.stream.connected) {
        notices.push("Live stream active.");
    } else if (state.stream.supported) {
        notices.push("Live stream reconnecting. Polling fallback remains available.");
    }

    if (state.ui.error) {
        globalBanner.textContent = state.ui.error;
        globalBanner.classList.remove("hidden");
        globalBanner.classList.add("error");
        return;
    }

    if (state.ui.loadingBoard || state.ui.loadingDetail || state.ui.actionPending) {
        notices.push("Workbench is syncing state.");
    }

    globalBanner.textContent = notices.join(" ");
    globalBanner.classList.remove("hidden");
    globalBanner.classList.remove("error");
}

function renderBoard() {
    document.querySelectorAll(".task-list").forEach((list) => {
        list.innerHTML = "";
    });

    if (state.ui.loadingBoard) {
        document.querySelectorAll(".task-list").forEach((list) => {
            list.innerHTML = '<div class="task-list-empty">Loading tasks...</div>';
        });
        updateColumnCounts([]);
        return;
    }

    const visibleTasks = getVisibleTasks();
    if (!visibleTasks.length) {
        document.querySelectorAll(".task-list").forEach((list) => {
            list.innerHTML = '<div class="task-list-empty">No tasks match the current filters. Create a task or loosen the filters.</div>';
        });
        updateColumnCounts([]);
        return;
    }

    visibleTasks.forEach((task) => {
        const latestRun = getLatestRun(task);
        const list = document.querySelector(`#col-${getStatusGroup(task.latestRunStatus)} .task-list`);
        if (list && latestRun) {
            list.appendChild(createTaskCard(task, latestRun));
        }
    });

    updateColumnCounts(visibleTasks);
}

function updateColumnCounts(visibleTasks) {
    columns.forEach((column) => {
        const group = column.dataset.statusGroup;
        const count = visibleTasks.filter((task) => getStatusGroup(task.latestRunStatus) === group).length;
        column.querySelector(".count").textContent = count.toString().padStart(2, "0");
    });
}

function createTaskCard(task, run) {
    const card = document.createElement("article");
    card.className = `task-card ${getRoleClass(run.primaryAgentRole || "")}`;
    if (task.id === state.selectedTaskId) {
        card.classList.add("selected");
    }

    card.innerHTML = `
        <div class="card-head">
            <span class="status-badge ${escapeHtml(run.status)}">${formatStatus(run.status)}</span>
        </div>
        <h4>${escapeHtml(task.title)}</h4>
        <p class="card-goal">${escapeHtml(task.goal)}</p>
        <div class="monologue-recessed">
            <span class="fact-label">${escapeHtml(run.primaryAgentRole || "Agent")}</span>
            <p>${escapeHtml(run.summary || "No summary yet.")}</p>
        </div>
        <div class="task-meta">
            <span class="role-chip">${escapeHtml(run.currentPhase || "plan")}</span>
            <span class="task-id">${task.id}</span>
        </div>
    `;

    card.addEventListener("click", async () => {
        state.selectedTaskId = task.id;
        await loadTaskDetail(task.id);
    });

    return card;
}

function renderSidebarSummary() {
    const runs = state.tasks.map((task) => getLatestRun(task)).filter(Boolean);
    document.getElementById("recentRunsCount").textContent = runs.length.toString().padStart(2, "0");
    document.getElementById("failedRunsCount").textContent = runs.filter((run) => run.status === "failed").length.toString().padStart(2, "0");
    document.getElementById("openTasksCount").textContent = runs.filter((run) => !["completed", "failed", "cancelled"].includes(run.status)).length.toString().padStart(2, "0");
}

function renderDetailPanel() {
    const task = getSelectedTask();
    const run = getSelectedRun();
    const detailEmptyState = document.getElementById("detailEmptyState");
    const detailContent = document.getElementById("detailContent");

    if (!task) {
        detailEmptyState.classList.remove("hidden");
        detailContent.classList.add("hidden");
        detailEmptyState.querySelector("h3").textContent = "No task selected";
        detailEmptyState.querySelector("p").textContent = "Select a card to inspect the latest run, artifacts, verdict, and follow-up actions.";
        return;
    }

    if (state.ui.loadingDetail) {
        detailEmptyState.classList.remove("hidden");
        detailContent.classList.add("hidden");
        detailEmptyState.querySelector("h3").textContent = "Loading task detail";
        detailEmptyState.querySelector("p").textContent = "Runs, artifacts, and verdict data are being loaded.";
        return;
    }

    detailEmptyState.classList.add("hidden");
    detailContent.classList.remove("hidden");

    document.getElementById("detailTaskTitle").textContent = task.title;
    document.getElementById("detailTaskPriority").textContent = task.priority;
    document.getElementById("detailTaskGoal").textContent = task.goal;

    renderConstraints(task.constraints, task.relatedPaths);
    renderRunHistory(state.runsByTaskId[task.id] || []);

    if (!run) {
        document.getElementById("detailRunStatus").textContent = "draft";
        document.getElementById("detailRunMode").textContent = "No runs";
        document.getElementById("detailRunStartedAt").textContent = "-";
        document.getElementById("detailRunProvider").textContent = "-";
        document.getElementById("detailRunSummary").textContent = "Create or start a run to inspect execution detail.";
        document.getElementById("detailRunCommand").textContent = "No command preview available.";
        document.getElementById("clineAvailability").textContent = state.meta.clineAvailable ? "available" : "unavailable";
        renderTimeline([]);
        renderEvents([]);
        renderArtifacts([]);
        renderChecklist([]);
        renderEvaluation(null, null);
        syncActionState(null);
        return;
    }

    const verdict = state.verdictsByRunId[run.id] || run.verdict;
    const artifacts = state.artifactsByRunId[run.id] || run.artifacts || [];
    const failureAnalysis = run.failureAnalysis || null;

    if (run.status === "orphaned" && (!verdict || verdict.decision === "pending")) {
        verdict.reason = verdict.reason || "This run was interrupted while the server restarted or the worker exited.";
        verdict.recommendedNextAction = verdict.recommendedNextAction || "retry_or_reopen";
        verdict.risks = verdict.risks?.length ? verdict.risks : ["The previous execution did not reach a terminal state"];
    }

    const detailRunStatus = document.getElementById("detailRunStatus");
    detailRunStatus.textContent = formatStatus(run.status);
    detailRunStatus.className = `status-badge ${run.status}`;
    document.getElementById("detailRunMode").textContent = MODE_LABELS[run.mode] || run.mode;
    document.getElementById("detailRunStartedAt").textContent = formatDate(run.startedAt);
    document.getElementById("detailRunProvider").textContent = `${run.runner?.provider || "mock"}${run.runner?.available ? "" : " unavailable"}`;
    document.getElementById("detailRunSummary").textContent = run.summary || "No run summary available.";
    document.getElementById("detailRunCommand").textContent = run.runner?.commandPreview || "No command preview available yet.";
    document.getElementById("clineAvailability").textContent = state.meta.clineAvailable ? "available" : "unavailable";

    renderTimeline(run.steps || []);
    renderEvents(run.events || []);
    renderArtifacts(artifacts);
    renderChecklist(run.planChecklist || []);
    renderEvaluation(verdict, failureAnalysis);
    syncActionState(run.status);
}

function renderConstraints(constraints = [], relatedPaths = []) {
    const container = document.getElementById("detailTaskConstraints");
    container.innerHTML = "";

    if (!constraints.length && !relatedPaths.length) {
        container.innerHTML = '<span class="constraint-pill">No explicit constraints</span>';
        return;
    }

    constraints.forEach((constraint) => {
        const pill = document.createElement("span");
        pill.className = "constraint-pill";
        pill.textContent = constraint;
        container.appendChild(pill);
    });

    relatedPaths.forEach((path) => {
        const pill = document.createElement("span");
        pill.className = "meta-pill";
        pill.textContent = path;
        container.appendChild(pill);
    });
}

function renderRunHistory(runs) {
    const list = document.getElementById("runHistoryList");
    list.innerHTML = "";

    if (!runs.length) {
        list.innerHTML = '<p class="empty-copy">No runs have been created for this task yet.</p>';
        return;
    }

    runs.forEach((run) => {
        const item = document.createElement("article");
        item.className = "run-history-item";
        if (run.id === state.selectedRunIdByTaskId[run.taskId]) {
            item.classList.add("selected");
        }
        item.innerHTML = `
            <div class="timeline-meta">
                <span class="meta-pill">${run.id}</span>
                <span class="status-badge subtle">${formatStatus(run.status)}</span>
            </div>
            <strong>${escapeHtml(MODE_LABELS[run.mode] || run.mode)}</strong>
            <p>${escapeHtml(run.summary || "No summary available.")}</p>
        `;
        item.addEventListener("click", async () => {
            state.selectedRunIdByTaskId[run.taskId] = run.id;
            await loadTaskDetail(run.taskId, run.id);
        });
        list.appendChild(item);
    });
}

function renderTimeline(steps) {
    const list = document.getElementById("timelineList");
    list.innerHTML = "";

    if (!steps.length) {
        list.innerHTML = '<p class="empty-copy">No timeline steps are available.</p>';
        return;
    }

    steps.forEach((step) => {
        const item = document.createElement("article");
        item.className = `timeline-item ${step.status || ""}`;
        item.innerHTML = `
            <div class="timeline-meta">
                <span class="meta-pill">${escapeHtml(step.phase)}</span>
                <span class="status-badge subtle">${formatStatus(step.status || "pending")}</span>
            </div>
            <strong>${escapeHtml(step.agentRole)}</strong>
            <p>${escapeHtml(step.summary)}</p>
        `;
        list.appendChild(item);
    });
}

function renderChecklist(items) {
    const summary = document.getElementById("checklistSummary");
    const list = document.getElementById("checklistList");
    list.innerHTML = "";

    if (!items.length) {
        summary.innerHTML = '<span class="meta-pill">No structured checklist yet</span>';
        list.innerHTML = '<p class="empty-copy">Cline has not emitted a task_progress checklist for this run.</p>';
        return;
    }

    const completedCount = items.filter((item) => item.done).length;
    summary.innerHTML = `
        <span class="meta-pill">${completedCount}/${items.length} completed</span>
        <span class="status-badge subtle">${items.length - completedCount} remaining</span>
    `;

    items.forEach((item) => {
        const row = document.createElement("article");
        row.className = `checklist-item${item.done ? " done" : ""}`;
        row.innerHTML = `
            <div class="timeline-meta">
                <span class="meta-pill">${item.done ? "done" : "pending"}</span>
                <span class="status-badge subtle">${formatDate(item.updatedAt)}</span>
            </div>
            <p>${escapeHtml(item.label)}</p>
        `;
        list.appendChild(row);
    });
}

function renderEvents(events) {
    const list = document.getElementById("eventList");
    list.innerHTML = "";

    if (!events.length) {
        list.innerHTML = '<p class="empty-copy">No live events have been recorded yet.</p>';
        return;
    }

    [...events].reverse().slice(0, 20).forEach((event) => {
        const item = document.createElement("article");
        item.className = "event-item";
        item.innerHTML = `
            <div class="timeline-meta">
                <span class="meta-pill">${escapeHtml(event.type || "event")}</span>
                <span class="status-badge subtle">${formatDate(event.ts)}</span>
            </div>
            <p>${escapeHtml(event.summary || "No summary available.")}</p>
        `;
        list.appendChild(item);
    });
}

function renderArtifacts(artifacts) {
    const list = document.getElementById("artifactList");
    list.innerHTML = "";

    if (!artifacts.length) {
        list.innerHTML = '<p class="empty-copy">No artifacts yet for this run.</p>';
        return;
    }

    artifacts.forEach((artifact) => {
        const item = document.createElement("article");
        item.className = `artifact-item${artifact.selected ? " selected" : ""}`;
        const shouldConstrainContent = shouldRenderArtifactInScrollBox(artifact);
        const contentClassName = shouldConstrainContent ? "artifact-content artifact-content-scrollable" : "artifact-content";
        item.innerHTML = `
            <div class="timeline-meta">
                <span class="meta-pill">${escapeHtml(artifact.type)}</span>
                ${artifact.selected ? '<span class="status-badge subtle">selected</span>' : ""}
            </div>
            <strong>${escapeHtml(artifact.title)}</strong>
            <p>${escapeHtml(artifact.path || "inline artifact")}</p>
            ${artifact.content ? `<pre class="${contentClassName}">${escapeHtml(artifact.content)}</pre>` : ""}
        `;
        list.appendChild(item);
    });
}

function shouldRenderArtifactInScrollBox(artifact) {
    if (!artifact?.content) {
        return false;
    }

    const lineCount = artifact.content.split("\n").length;
    const isInlineArtifact = !artifact.path;
    return isInlineArtifact || lineCount > ARTIFACT_SCROLL_LINE_THRESHOLD || artifact.content.length > ARTIFACT_SCROLL_CHAR_THRESHOLD;
}

function renderEvaluation(verdict, failureAnalysis) {
    document.getElementById("detailVerdictDecision").textContent = verdict?.decision || "pending";
    document.getElementById("detailVerdictAction").textContent = (verdict?.recommendedNextAction || "waiting").replaceAll("_", " ");
    document.getElementById("detailVerdictReason").textContent = verdict?.reason || "No verdict available yet.";
    renderRisks(verdict?.risks || []);
    document.getElementById("detailFailureStage").textContent = formatFailureValue(failureAnalysis?.failureStage);
    document.getElementById("detailFailureType").textContent = formatFailureValue(failureAnalysis?.failureType);
    document.getElementById("detailFailureRootCause").textContent = failureAnalysis?.rootCauseHypothesis || "No failure analysis recorded.";
    document.getElementById("detailFailureFix").textContent = failureAnalysis?.recommendedFix || "No remediation guidance recorded.";
    document.getElementById("detailSkillGap").textContent = formatFailureValue(failureAnalysis?.skillGap);
    document.getElementById("detailSkillSeed").textContent = failureAnalysis?.skillSeed || "No skill candidate recorded.";
    renderFailureEvidence(failureAnalysis?.evidence || []);
}

function renderRisks(risks) {
    const container = document.getElementById("detailVerdictRisks");
    container.innerHTML = "";

    if (!risks.length) {
        container.innerHTML = '<span class="risk-pill">No explicit risks</span>';
        return;
    }

    risks.forEach((risk) => {
        const pill = document.createElement("span");
        pill.className = "risk-pill";
        pill.textContent = risk;
        container.appendChild(pill);
    });
}

function renderFailureEvidence(evidence) {
    const container = document.getElementById("detailFailureEvidence");
    container.innerHTML = "";

    if (!evidence.length) {
        container.innerHTML = '<span class="risk-pill">No structured evidence recorded</span>';
        return;
    }

    evidence.forEach((entry) => {
        const item = document.createElement("article");
        item.className = "artifact-item";
        item.innerHTML = `
            <span class="fact-label">Evidence</span>
            <p>${escapeHtml(entry)}</p>
        `;
        container.appendChild(item);
    });
}

function syncActionState(status) {
    const disabled = state.ui.actionPending || state.ui.loadingDetail;
    retryBtn.textContent = getPrimaryRunActionLabel(status);
    retryBtn.disabled = disabled;
    reopenBtn.disabled = disabled;
    approveBtn.disabled = disabled;
    cancelRunBtn.disabled = disabled;
    deleteTaskBtn.disabled = disabled;

    if (!status) {
        retryBtn.textContent = "Start Run";
        retryBtn.disabled = false;
        reopenBtn.disabled = true;
        approveBtn.disabled = true;
        cancelRunBtn.disabled = true;
        deleteTaskBtn.disabled = false;
        return;
    }

    if (["draft", "planned"].includes(status)) {
        approveBtn.disabled = true;
        cancelRunBtn.disabled = true;
    }

    if (status === "running" || status === "revising") {
        approveBtn.disabled = true;
        reopenBtn.disabled = true;
        deleteTaskBtn.disabled = true;
    }

    if (status === "completed") {
        approveBtn.disabled = true;
        cancelRunBtn.disabled = true;
    }

    if (status === "cancelled" || status === "failed" || status === "orphaned") {
        reopenBtn.disabled = false;
        cancelRunBtn.disabled = true;
        approveBtn.disabled = true;
        deleteTaskBtn.disabled = false;
    }
}

function getPrimaryRunAction(status) {
    if (!status || ["draft", "planned"].includes(status)) {
        return "start";
    }
    return "retry";
}

function getPrimaryRunActionLabel(status) {
    return getPrimaryRunAction(status) === "start" ? "Start Run" : "Retry";
}

function openTaskModal() {
    modal.classList.remove("hidden");
    taskTitleInput.focus();
}

function closeTaskModal() {
    modal.classList.add("hidden");
    taskTitleInput.value = "";
    taskGoalInput.value = "";
    taskConstraintsInput.value = "";
    taskPathsInput.value = "";
    taskModeInput.value = "plan-execute-eval";
    taskPriorityInput.value = "medium";
}

function getVisibleTasks() {
    return state.tasks.filter((task) => {
        const latestRun = getLatestRun(task);
        const matchesStatus = state.filters.status === "all" || task.latestRunStatus === state.filters.status;
        return matchesStatus && latestRun;
    });
}

function getLatestRun(task) {
    const runs = state.runsByTaskId[task.id];
    if (runs?.length) {
        return runs.find((run) => run.id === task.latestRunId) || runs[0];
    }
    return task.latestRun || null;
}

function getSelectedTask() {
    return state.tasks.find((task) => task.id === state.selectedTaskId) || null;
}

function getSelectedRun() {
    const task = getSelectedTask();
    if (!task) {
        return null;
    }
    const selectedRunId = state.selectedRunIdByTaskId[task.id] || task.latestRunId;
    const runs = state.runsByTaskId[task.id] || [];
    return runs.find((run) => run.id === selectedRunId) || getLatestRun(task);
}

function removeTaskFromState(taskId) {
    state.tasks = state.tasks.filter((task) => task.id !== taskId);
    delete state.runsByTaskId[taskId];
    delete state.selectedRunIdByTaskId[taskId];
    if (state.selectedTaskId === taskId) {
        state.selectedTaskId = null;
    }
}

function getStatusGroup(status) {
    return Object.entries(BOARD_GROUPS).find(([, statuses]) => statuses.includes(status))?.[0] || "queue";
}

function getRoleClass(role) {
    const value = role.toLowerCase();
    if (value.includes("executor")) {
        return "role-executor";
    }
    if (value.includes("evaluator")) {
        return "role-evaluator";
    }
    return "";
}

function formatStatus(status) {
    return status.replaceAll("_", " ");
}

function formatFailureValue(value) {
    if (!value) {
        return "-";
    }
    return value.replaceAll("_", " ");
}

function formatDate(value) {
    if (!value) {
        return "-";
    }
    return new Intl.DateTimeFormat("ko-KR", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(new Date(value));
}

function splitMultiline(value) {
    return value
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean);
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

initWorkbench();
