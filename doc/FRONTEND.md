# Frontend Development & API Integration Guide

이 문서는 칸반보드 프론트엔드의 설계 구조와 백엔드 연동을 위한 규격을 설명합니다.

## 1. 디자인 시스템 토큰 (Design Tokens)

`static/styles.css`에 정의된 주요 테마 변수입니다.

| Token | Value | Description |
| :--- | :--- | :--- |
| `--bg-deep` | `#0b1326` | 전체 대시보드 배경 |
| `--surface-high` | `#2d3449` | 카드 및 인터랙티브 요소 배경 |
| `--primary` | `#adc6ff` | Planner 역할 및 주요 액션 컬러 |
| `--secondary` | `#ddb7ff` | Executor 역할 컬러 |
| `--tertiary` | `#4fdbc8` | Evaluator 역할 컬러 |

## 2. API 연동 규격 (Proposed)

백엔드에서 구현해야 할 REST API 엔드포인트 제안입니다.

### 2.1 태스크 목록 조회
- **Endpoint**: `GET /api/tasks`
- **Response Body**:
```json
[
  {
    "id": "1",
    "title": "Task Title",
    "status": "todo",
    "role": "Planner"
  }
]
```

### 2.2 태스크 상태 업데이트
- **Endpoint**: `PATCH /api/tasks/{id}`
- **Request Body**:
```json
{
  "status": "in-progress"
}
```

### 2.3 태스크 생성
- **Endpoint**: `POST /api/tasks`
- **Request Body**:
```json
{
  "title": "New Task",
  "role": "Planner"
}
```

## 3. 프론트엔드 구조

- **index.html**: Semantic HTML5 구조로 되어 있으며, Sidebar와 Kanban Board 영역으로 나뉩니다.
- **styles.css**: **Glassmorphism**(유리 효과)과 **No-Line**(테두리 최소화) 디자인 원칙이 적용되어 있습니다.
- **app.js**:
    - `taskState`: 현재 클라이언트측 상태를 관리합니다.
    - `setupDragAndDrop()`: 브라우저 Native Drag & Drop API를 사용하여 구현되었습니다.
    - `updateTaskStatus()`: 상태 변경 시 호출되는 함수로, 이곳에 백엔드 API 연동 로직을 추가하면 됩니다.

## 4. 실행 방법

`uv`를 사용하여 서버를 실행합니다. 실행 시 로컬 네트워크 IP 주소가 출력되어 윈도우 PC에서 바로 접속할 수 있습니다.

```bash
uv run main.py
```

브라우저에서 출력된 `http://<IP>:8000` 주소로 접속하면 동작을 확인할 수 있습니다.
