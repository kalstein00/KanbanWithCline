/**
 * The Orchestrator's Lens: task + latestRun workbench mock
 */

const BOARD_GROUPS = {
    queue: ['draft', 'planned'],
    stream: ['running', 'awaiting_review', 'revising'],
    synthesis: ['completed', 'failed', 'cancelled']
};

const TYPE_LABELS = {
    document_analysis: 'Document Analysis',
    prd_generation: 'PRD Generation',
    debugging: 'Debugging',
    test_writing: 'Test Writing'
};

const MODE_LABELS = {
    'plan-execute-eval': 'Planner -> Executor -> Evaluator',
    'single-agent': 'Single Agent',
    'debate': 'Debate'
};

const state = {
    tasks: [
        {
            id: 'task_001',
            title: 'Legacy design docs to product PRD conversion',
            type: 'prd_generation',
            goal: 'Analyze the existing concept docs and produce a product PRD with explicit run and artifact models.',
            constraints: ['Keep the current visual language', 'Preserve MVP scope'],
            priority: 'high',
            createdAt: '2026-04-18T09:10:00Z',
            latestRunId: 'run_001',
            latestRunStatus: 'awaiting_review'
        },
        {
            id: 'task_002',
            title: 'FastAPI 500 error root cause isolation',
            type: 'debugging',
            goal: 'Reproduce the failure, isolate the root cause, and recommend the lowest-risk fix path.',
            constraints: ['Do not mutate production data'],
            priority: 'high',
            createdAt: '2026-04-18T09:45:00Z',
            latestRunId: 'run_002',
            latestRunStatus: 'running'
        },
        {
            id: 'task_003',
            title: 'Service layer regression test coverage',
            type: 'test_writing',
            goal: 'Add missing tests around edge-case validation paths and failure responses.',
            constraints: ['Avoid snapshot tests'],
            priority: 'medium',
            createdAt: '2026-04-18T10:05:00Z',
            latestRunId: 'run_003',
            latestRunStatus: 'completed'
        },
        {
            id: 'task_004',
            title: 'Architecture notes ingestion plan',
            type: 'document_analysis',
            goal: 'Summarize architecture notes and identify unresolved assumptions before implementation starts.',
            constraints: ['Call out open issues explicitly'],
            priority: 'medium',
            createdAt: '2026-04-18T10:20:00Z',
            latestRunId: 'run_004',
            latestRunStatus: 'planned'
        }
    ],
    runsByTaskId: {
        task_001: [
            {
                id: 'run_001',
                taskId: 'task_001',
                mode: 'plan-execute-eval',
                status: 'awaiting_review',
                startedAt: '2026-04-18T09:15:00Z',
                currentPhase: 'eval',
                primaryAgentRole: 'Evaluator',
                summary: 'Evaluator flagged missing task-run relationship definitions and API path ambiguity.',
                steps: [
                    { id: 'step_001', phase: 'plan', agentRole: 'Planner', status: 'completed', summary: 'Mapped legacy docs into product and frontend workstreams.' },
                    { id: 'step_002', phase: 'execute', agentRole: 'Cline Executor', status: 'completed', summary: 'Drafted product and frontend PRD documents.' },
                    { id: 'step_003', phase: 'eval', agentRole: 'Evaluator', status: 'completed', summary: 'Requested clearer ownership for task, run, artifact, and verdict entities.' }
                ],
                artifacts: [
                    { id: 'artifact_001', type: 'document', title: 'PRODUCT-PRD.md', path: 'doc/PRODUCT-PRD.md', selected: true },
                    { id: 'artifact_002', type: 'document', title: 'FRONTEND.md', path: 'doc/FRONTEND.md', selected: false }
                ],
                verdict: {
                    decision: 'revise',
                    reason: 'The document structure is sound, but task-run ownership and endpoint semantics need to be locked before implementation.',
                    risks: ['Frontend and backend may diverge on status ownership', 'Retry and approval actions remain underspecified'],
                    recommendedNextAction: 'retry_with_critique'
                }
            }
        ],
        task_002: [
            {
                id: 'run_002',
                taskId: 'task_002',
                mode: 'debate',
                status: 'running',
                startedAt: '2026-04-18T09:52:00Z',
                currentPhase: 'execute',
                primaryAgentRole: 'Cline Executor',
                summary: 'Executor is tracing request lifecycles while a parallel evaluator watches for regression risks.',
                steps: [
                    { id: 'step_004', phase: 'plan', agentRole: 'Planner', status: 'completed', summary: 'Generated two likely causes around serialization and dependency injection.' },
                    { id: 'step_005', phase: 'execute', agentRole: 'Cline Executor', status: 'running', summary: 'Inspecting server logs and reproducing the error against a local fixture.' },
                    { id: 'step_006', phase: 'eval', agentRole: 'Evaluator', status: 'pending', summary: 'Waiting for the executor patch candidate.' }
                ],
                artifacts: [
                    { id: 'artifact_003', type: 'log', title: 'uvicorn trace summary', path: 'logs/debug-trace.md', selected: true }
                ],
                verdict: {
                    decision: 'pending',
                    reason: 'Execution is still underway.',
                    risks: ['Root cause not confirmed yet'],
                    recommendedNextAction: 'continue_run'
                }
            }
        ],
        task_003: [
            {
                id: 'run_003',
                taskId: 'task_003',
                mode: 'plan-execute-eval',
                status: 'completed',
                startedAt: '2026-04-18T10:07:00Z',
                currentPhase: 'eval',
                primaryAgentRole: 'Evaluator',
                summary: 'Tests cover success, validation failure, and invalid state transitions.',
                steps: [
                    { id: 'step_007', phase: 'plan', agentRole: 'Planner', status: 'completed', summary: 'Outlined core scenarios and edge cases.' },
                    { id: 'step_008', phase: 'execute', agentRole: 'Cline Executor', status: 'completed', summary: 'Added unit tests for validation and failure branches.' },
                    { id: 'step_009', phase: 'eval', agentRole: 'Evaluator', status: 'completed', summary: 'Approved result after checking missing flaky patterns.' }
                ],
                artifacts: [
                    { id: 'artifact_004', type: 'test', title: 'service_test.py patch', path: 'tests/service_test.py', selected: true }
                ],
                verdict: {
                    decision: 'approved',
                    reason: 'The selected artifact meets the required test coverage and risk profile.',
                    risks: ['Future schema changes may require fixture updates'],
                    recommendedNextAction: 'approve'
                }
            }
        ],
        task_004: [
            {
                id: 'run_004',
                taskId: 'task_004',
                mode: 'single-agent',
                status: 'planned',
                startedAt: '2026-04-18T10:22:00Z',
                currentPhase: 'plan',
                primaryAgentRole: 'Planner',
                summary: 'Task has been scoped but execution has not started.',
                steps: [
                    { id: 'step_010', phase: 'plan', agentRole: 'Planner', status: 'completed', summary: 'Captured the document set and expected output sections.' }
                ],
                artifacts: [],
                verdict: {
                    decision: 'queued',
                    reason: 'Waiting for execution.',
                    risks: ['Assumptions in the notes may still be outdated'],
                    recommendedNextAction: 'start_run'
                }
            }
        ]
    },
    selectedTaskId: 'task_001',
    filters: {
        type: 'all',
        status: 'all'
    }
};

const columns = document.querySelectorAll('.column');
const modal = document.getElementById('taskModal');
const addTaskBtn = document.getElementById('addTaskBtn');
const cancelBtn = document.getElementById('cancelBtn');
const saveBtn = document.getElementById('saveBtn');
const taskTitleInput = document.getElementById('taskTitleInput');
const taskTypeInput = document.getElementById('taskTypeInput');
const taskGoalInput = document.getElementById('taskGoalInput');
const taskModeInput = document.getElementById('taskModeInput');
const taskTypeFilter = document.getElementById('taskTypeFilter');
const statusFilter = document.getElementById('statusFilter');
const retryBtn = document.getElementById('retryBtn');
const reopenBtn = document.getElementById('reopenBtn');
const approveBtn = document.getElementById('approveBtn');

function initWorkbench() {
    bindEvents();
    renderWorkbench();
}

function bindEvents() {
    addTaskBtn.addEventListener('click', openTaskModal);
    cancelBtn.addEventListener('click', closeTaskModal);
    saveBtn.addEventListener('click', createTask);

    taskTypeFilter.addEventListener('change', (event) => {
        state.filters.type = event.target.value;
        renderWorkbench();
    });

    statusFilter.addEventListener('change', (event) => {
        state.filters.status = event.target.value;
        renderWorkbench();
    });

    retryBtn.addEventListener('click', () => triggerRunAction('retry'));
    reopenBtn.addEventListener('click', () => triggerRunAction('reopen'));
    approveBtn.addEventListener('click', () => triggerRunAction('approve'));
}

function renderWorkbench() {
    renderBoard();
    renderSidebarSummary();
    renderDetailPanel();
}

function getLatestRun(task) {
    return (state.runsByTaskId[task.id] || []).find((run) => run.id === task.latestRunId) || null;
}

function getStatusGroup(status) {
    return Object.entries(BOARD_GROUPS).find(([, statuses]) => statuses.includes(status))?.[0] || 'queue';
}

function getVisibleTasks() {
    return state.tasks.filter((task) => {
        const latestRun = getLatestRun(task);
        const matchesType = state.filters.type === 'all' || task.type === state.filters.type;
        const matchesStatus = state.filters.status === 'all' || task.latestRunStatus === state.filters.status;
        return matchesType && matchesStatus && latestRun;
    });
}

function renderBoard() {
    document.querySelectorAll('.task-list').forEach((list) => {
        list.innerHTML = '';
    });

    const visibleTasks = getVisibleTasks();

    visibleTasks.forEach((task) => {
        const list = document.querySelector(`#col-${getStatusGroup(task.latestRunStatus)} .task-list`);
        if (list) {
            list.appendChild(createTaskCard(task, getLatestRun(task)));
        }
    });

    columns.forEach((column) => {
        const group = column.dataset.statusGroup;
        const count = visibleTasks.filter((task) => getStatusGroup(task.latestRunStatus) === group).length;
        column.querySelector('.count').innerText = count.toString().padStart(2, '0');
    });
}

function createTaskCard(task, run) {
    const card = document.createElement('article');
    card.className = `task-card ${getRoleClass(run.primaryAgentRole)}`;
    if (task.id === state.selectedTaskId) {
        card.classList.add('selected');
    }

    card.innerHTML = `
        <div class="card-head">
            <span class="meta-pill">${TYPE_LABELS[task.type] || task.type}</span>
            <span class="status-badge">${formatStatus(run.status)}</span>
        </div>
        <h4>${task.title}</h4>
        <p class="card-goal">${task.goal}</p>
        <div class="monologue-recessed">
            <span class="fact-label">${run.primaryAgentRole}</span>
            <p>${run.summary}</p>
        </div>
        <div class="task-meta">
            <span class="role-chip">${run.currentPhase}</span>
            <span class="task-id">${task.id}</span>
        </div>
    `;

    card.addEventListener('click', () => {
        state.selectedTaskId = task.id;
        renderWorkbench();
    });

    return card;
}

function renderSidebarSummary() {
    const allRuns = state.tasks.map((task) => getLatestRun(task)).filter(Boolean);
    document.getElementById('recentRunsCount').textContent = allRuns.length.toString().padStart(2, '0');
    document.getElementById('failedRunsCount').textContent = allRuns.filter((run) => run.status === 'failed').length.toString().padStart(2, '0');
    document.getElementById('openTasksCount').textContent = allRuns.filter((run) => !['completed', 'failed', 'cancelled'].includes(run.status)).length.toString().padStart(2, '0');
}

function renderDetailPanel() {
    const task = state.tasks.find((item) => item.id === state.selectedTaskId);
    const run = task ? getLatestRun(task) : null;
    const detailEmptyState = document.getElementById('detailEmptyState');
    const detailContent = document.getElementById('detailContent');

    if (!task || !run) {
        detailEmptyState.classList.remove('hidden');
        detailContent.classList.add('hidden');
        return;
    }

    detailEmptyState.classList.add('hidden');
    detailContent.classList.remove('hidden');

    document.getElementById('detailTaskTitle').textContent = task.title;
    document.getElementById('detailTaskType').textContent = TYPE_LABELS[task.type] || task.type;
    document.getElementById('detailTaskPriority').textContent = task.priority;
    document.getElementById('detailTaskGoal').textContent = task.goal;
    document.getElementById('detailRunStatus').textContent = formatStatus(run.status);
    document.getElementById('detailRunMode').textContent = MODE_LABELS[run.mode] || run.mode;
    document.getElementById('detailRunStartedAt').textContent = formatDate(run.startedAt);
    document.getElementById('detailVerdictDecision').textContent = run.verdict.decision;
    document.getElementById('detailVerdictAction').textContent = run.verdict.recommendedNextAction.replaceAll('_', ' ');
    document.getElementById('detailVerdictReason').textContent = run.verdict.reason;

    renderConstraints(task.constraints);
    renderTimeline(run.steps);
    renderArtifacts(run.artifacts);
    renderRisks(run.verdict.risks);
    syncActionState(run.status);
}

function renderConstraints(constraints) {
    const container = document.getElementById('detailTaskConstraints');
    container.innerHTML = '';
    constraints.forEach((constraint) => {
        const pill = document.createElement('span');
        pill.className = 'constraint-pill';
        pill.textContent = constraint;
        container.appendChild(pill);
    });
}

function renderTimeline(steps) {
    const list = document.getElementById('timelineList');
    list.innerHTML = '';
    steps.forEach((step) => {
        const item = document.createElement('article');
        item.className = `timeline-item ${step.status}`;
        item.innerHTML = `
            <div class="timeline-meta">
                <span class="meta-pill">${step.phase}</span>
                <span class="status-badge subtle">${formatStatus(step.status)}</span>
            </div>
            <strong>${step.agentRole}</strong>
            <p>${step.summary}</p>
        `;
        list.appendChild(item);
    });
}

function renderArtifacts(artifacts) {
    const list = document.getElementById('artifactList');
    list.innerHTML = '';

    if (!artifacts.length) {
        list.innerHTML = '<p class="empty-copy">No artifacts yet for this run.</p>';
        return;
    }

    artifacts.forEach((artifact) => {
        const item = document.createElement('article');
        item.className = `artifact-item${artifact.selected ? ' selected' : ''}`;
        item.innerHTML = `
            <div class="timeline-meta">
                <span class="meta-pill">${artifact.type}</span>
                ${artifact.selected ? '<span class="status-badge subtle">selected</span>' : ''}
            </div>
            <strong>${artifact.title}</strong>
            <p>${artifact.path}</p>
        `;
        list.appendChild(item);
    });
}

function renderRisks(risks) {
    const container = document.getElementById('detailVerdictRisks');
    container.innerHTML = '';
    risks.forEach((risk) => {
        const pill = document.createElement('span');
        pill.className = 'risk-pill';
        pill.textContent = risk;
        container.appendChild(pill);
    });
}

function syncActionState(status) {
    retryBtn.disabled = false;
    reopenBtn.disabled = false;
    approveBtn.disabled = false;

    if (status === 'running') {
        approveBtn.disabled = true;
    }

    if (status === 'completed') {
        approveBtn.disabled = true;
    }

    if (status === 'planned') {
        reopenBtn.disabled = true;
    }
}

function openTaskModal() {
    modal.classList.remove('hidden');
    taskTitleInput.focus();
}

function closeTaskModal() {
    modal.classList.add('hidden');
    taskTitleInput.value = '';
    taskGoalInput.value = '';
    taskTypeInput.value = 'document_analysis';
    taskModeInput.value = 'plan-execute-eval';
}

function createTask() {
    const title = taskTitleInput.value.trim();
    const goal = taskGoalInput.value.trim();
    const type = taskTypeInput.value;
    const mode = taskModeInput.value;

    if (!title || !goal) {
        window.alert('Title and goal are required.');
        return;
    }

    const taskId = `task_${Math.random().toString(36).slice(2, 8)}`;
    const runId = `run_${Math.random().toString(36).slice(2, 8)}`;

    const newTask = {
        id: taskId,
        title,
        type,
        goal,
        constraints: ['New task created from workbench UI'],
        priority: 'medium',
        createdAt: new Date().toISOString(),
        latestRunId: runId,
        latestRunStatus: 'draft'
    };

    const newRun = {
        id: runId,
        taskId,
        mode,
        status: 'draft',
        startedAt: new Date().toISOString(),
        currentPhase: 'plan',
        primaryAgentRole: 'Planner',
        summary: 'Task is queued for orchestration and waiting for execution.',
        steps: [
            { id: `step_${Math.random().toString(36).slice(2, 8)}`, phase: 'plan', agentRole: 'Planner', status: 'pending', summary: 'Planning has not started yet.' }
        ],
        artifacts: [],
        verdict: {
            decision: 'queued',
            reason: 'No execution has started yet.',
            risks: ['Context may still be incomplete'],
            recommendedNextAction: 'start_run'
        }
    };

    state.tasks.unshift(newTask);
    state.runsByTaskId[taskId] = [newRun];
    state.selectedTaskId = taskId;
    closeTaskModal();
    renderWorkbench();
}

function triggerRunAction(action) {
    const task = state.tasks.find((item) => item.id === state.selectedTaskId);
    if (!task) {
        return;
    }

    const runs = state.runsByTaskId[task.id];
    const latestRun = getLatestRun(task);
    if (!latestRun) {
        return;
    }

    if (action === 'retry') {
        const runId = `run_${Math.random().toString(36).slice(2, 8)}`;
        const newRun = {
            id: runId,
            taskId: task.id,
            mode: latestRun.mode,
            status: 'revising',
            startedAt: new Date().toISOString(),
            currentPhase: 'execute',
            primaryAgentRole: 'Cline Executor',
            summary: 'Retry started with critique from the previous verdict.',
            steps: [
                { id: `step_${Math.random().toString(36).slice(2, 8)}`, phase: 'plan', agentRole: 'Planner', status: 'completed', summary: 'Critique was transformed into a revised execution plan.' },
                { id: `step_${Math.random().toString(36).slice(2, 8)}`, phase: 'execute', agentRole: 'Cline Executor', status: 'running', summary: 'A new attempt is underway with tighter acceptance criteria.' }
            ],
            artifacts: [],
            verdict: {
                decision: 'pending',
                reason: 'Retry execution has just started.',
                risks: ['Result is still unverified'],
                recommendedNextAction: 'continue_run'
            }
        };

        runs.unshift(newRun);
        task.latestRunId = runId;
        task.latestRunStatus = 'revising';
    }

    if (action === 'approve') {
        latestRun.status = 'completed';
        latestRun.currentPhase = 'eval';
        latestRun.summary = 'Run approved by the user from the workbench.';
        latestRun.verdict.decision = 'approved';
        latestRun.verdict.reason = 'The user accepted the current result.';
        latestRun.verdict.recommendedNextAction = 'approved';
        task.latestRunStatus = 'completed';
    }

    if (action === 'reopen') {
        latestRun.status = 'planned';
        latestRun.currentPhase = 'plan';
        latestRun.summary = 'Run reopened and moved back to planning.';
        latestRun.verdict.decision = 'queued';
        latestRun.verdict.reason = 'The user requested a reopened planning cycle.';
        latestRun.verdict.recommendedNextAction = 'start_run';
        task.latestRunStatus = 'planned';
    }

    renderWorkbench();
}

function getRoleClass(role) {
    if (role.toLowerCase().includes('executor')) {
        return 'role-executor';
    }
    if (role.toLowerCase().includes('evaluator')) {
        return 'role-evaluator';
    }
    return '';
}

function formatStatus(status) {
    return status.replaceAll('_', ' ');
}

function formatDate(value) {
    return new Intl.DateTimeFormat('ko-KR', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    }).format(new Date(value));
}

initWorkbench();
