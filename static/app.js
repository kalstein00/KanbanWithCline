/**
 * The Orchestrator’s Lens: Design-led logic
 */

const taskState = {
    tasks: [
        { 
            id: '1', 
            title: '에이전트 계층 구조 설계', 
            status: 'todo', 
            role: 'Planner',
            monologue: '중앙 집중형 제어 시스템을 위해 노드 간의 통신 규약을 먼저 정의해야 한다.'
        },
        { 
            id: '2', 
            title: 'FastAPI 기반 API 인터페이스 구축', 
            status: 'in-progress', 
            role: 'Executor',
            monologue: 'Uvicorn 프로세스 격리를 통해 성능 최적화를 진행 중...'
        },
        { 
            id: '3', 
            title: '디자인 시스템 토큰 추출 및 문서화', 
            status: 'done', 
            role: 'Evaluator',
            monologue: 'Stitch 레퍼런스 이미지와의 픽셀 매칭률 98% 달성.'
        },
        { 
            id: '4', 
            title: '드래그 앤 드롭 애니메이션 고도화', 
            status: 'todo', 
            role: 'Executor',
            monologue: 'Cubic-bezier 곡선을 사용하여 더 유기적인 흐름을 유도함.'
        }
    ]
};

// Selectors
const columns = document.querySelectorAll('.column');
const modal = document.getElementById('taskModal');
const addTaskBtn = document.getElementById('addTaskBtn');
const cancelBtn = document.getElementById('cancelBtn');
const saveBtn = document.getElementById('saveBtn');
const taskInput = document.getElementById('taskInput');

// Initialize Board
function initBoard() {
    renderTasks();
    setupDragAndDrop();
}

// Render Tasks to UI
function renderTasks() {
    // Clear lists
    document.querySelectorAll('.task-list').forEach(list => list.innerHTML = '');
    
    // Distribute tasks
    taskState.tasks.forEach(task => {
        const list = document.querySelector(`#col-${task.status} .task-list`);
        if (list) {
            list.appendChild(createTaskCard(task));
        }
    });

    // Update counts (01, 02 style)
    document.querySelectorAll('.column').forEach((col, idx) => {
        const count = col.querySelector('.count');
        const tasksInCol = taskState.tasks.filter(t => t.status === col.dataset.status).length;
        count.innerText = tasksInCol.toString().padStart(2, '0');
    });
}

// Create Task Card DOM element with "The Orchestrator's Lens" details
function createTaskCard(task) {
    const card = document.createElement('article');
    const roleClass = task.role === 'Executor' ? 'role-executor' : 
                     task.role === 'Evaluator' ? 'role-evaluator' : '';
    
    card.className = `task-card ${roleClass}`;
    card.draggable = true;
    card.dataset.id = task.id;
    
    // Nested Float: Internal Monologue card inside the task card
    card.innerHTML = `
        <h4>${task.title}</h4>
        ${task.monologue ? `<div class="monologue-recessed">${task.monologue}</div>` : ''}
        <div class="task-meta">
            <span class="role-chip">${task.role}</span>
            <span class="task-id">#${task.id.slice(-4)}</span>
        </div>
    `;

    card.addEventListener('dragstart', (e) => {
        card.classList.add('dragging');
        e.dataTransfer.setData('text/plain', task.id);
        
        // Custom drag image if needed later
    });

    card.addEventListener('dragend', () => {
        card.classList.remove('dragging');
    });

    return card;
}

// Drag and Drop Logic
function setupDragAndDrop() {
    columns.forEach(column => {
        column.addEventListener('dragover', (e) => {
            e.preventDefault();
            column.classList.add('drag-over');
        });

        column.addEventListener('dragleave', () => {
            column.classList.remove('drag-over');
        });

        column.addEventListener('drop', (e) => {
            e.preventDefault();
            column.classList.remove('drag-over');
            
            const taskId = e.dataTransfer.getData('text/plain');
            const newStatus = column.dataset.status;
            
            updateTaskStatus(taskId, newStatus);
        });
    });
}

// Update state and re-render
function updateTaskStatus(id, newStatus) {
    const taskIndex = taskState.tasks.findIndex(t => t.id === id);
    if (taskIndex > -1) {
        taskState.tasks[taskIndex].status = newStatus;
        renderTasks();
        
        // Visual feedback
        console.log(`[SYNCHRONIZED] Task ${id} -> ${newStatus}`);
    }
}

// Event Listeners for Modal
addTaskBtn.addEventListener('click', () => {
    modal.classList.remove('hidden');
    taskInput.focus();
});

cancelBtn.addEventListener('click', () => {
    modal.classList.add('hidden');
    taskInput.value = '';
});

saveBtn.addEventListener('click', () => {
    const title = taskInput.value.trim();
    if (title) {
        const roles = ['Planner', 'Executor', 'Evaluator'];
        const randomRole = roles[Math.floor(Math.random() * roles.length)];
        
        const newTask = {
            id: Math.random().toString(36).substr(2, 9),
            title: title,
            status: 'todo',
            role: randomRole,
            monologue: '새로운 에이전트 프로세스가 시작되었습니다...'
        };
        taskState.tasks.push(newTask);
        renderTasks();
        modal.classList.add('hidden');
        taskInput.value = '';
    }
});

// App Start
initBoard();
