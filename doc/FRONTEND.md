# Frontend Specification: Agent Orchestration Workbench

이 문서는 `doc/PRODUCT-PRD.md`를 기준으로 프런트엔드가 어떤 정보 구조, 상태, API 계약, 화면 동작을 가져야 하는지 정의한다.

현재 구현은 정적 칸반 목업 수준이지만, 목표는 개발자용 `Agent Orchestration Workbench`로 확장하는 것이다.

## 1. 프런트엔드 목표

프런트엔드는 단순 task 보드가 아니라 다음을 수행해야 한다.

- 사용자가 task를 생성하고 실행 맥락을 입력할 수 있어야 한다.
- task별 run 진행 상태를 추적할 수 있어야 한다.
- planner, executor, evaluator, cline 같은 agent 역할을 구분해 보여줘야 한다.
- artifact와 verdict를 확인하고 결과를 채택하거나 재실행할 수 있어야 한다.
- 문서 분석, PRD 작성, 디버깅, 테스트 작성 같은 범용 task를 한 UI에서 다룰 수 있어야 한다.

## 2. 디자인 시스템 토큰

현재 프런트엔드는 라이트 모드 기반의 `The Orchestrator's Lens` 디자인 시스템을 사용한다.
주요 토큰은 `static/styles.css` 기준으로 아래와 같다.

| Token | Value | Description |
| :--- | :--- | :--- |
| `--background` | `#FFFFFF` | 전체 앱 배경 |
| `--surface-container-low` | `#F8F9FA` | 사이드바 및 낮은 강도의 표면 |
| `--surface-container` | `#F0F2F5` | 기본 인터랙션 표면 |
| `--surface-container-high` | `#E1E3E6` | 강조된 인터랙티브 표면 |
| `--on-surface` | `#1A1C1E` | 기본 텍스트 컬러 |
| `--on-surface-variant` | `#44474E` | 보조 텍스트 컬러 |
| `--primary` | `#005AC2` | Planner 및 주요 액션 컬러 |
| `--secondary` | `#6B3D91` | Executor 컬러 |
| `--tertiary` | `#006A60` | Evaluator 컬러 |
| `--glass-bg` | `rgba(255, 255, 255, 0.7)` | 카드/모달용 글래스 배경 |

### 2.1 디자인 원칙

- 라이트 모드 화이트 배경을 기본값으로 사용한다.
- No-Line 원칙에 따라 강한 border 대신 표면 대비와 그림자로 구획을 나눈다.
- 역할 구분은 색상 토큰과 메타 정보 조합으로 드러낸다.
- 카드와 모달은 light glassmorphism 스타일을 사용한다.
- 시각 장식보다 상태 전달과 정보 위계를 우선한다.

## 3. 핵심 화면 구조

초기 MVP 기준 화면은 3개 영역으로 나눈다.

### 3.1 Sidebar

역할:

- 현재 시스템 상태 요약
- agent 역할별 상태 또는 처리량 요약
- 선택된 orchestration mode 요약
- 전역 필터 또는 향후 빠른 탐색 진입점

현재 구현:

- 로고
- Planner / Executor / Evaluator stat bar

후속 확장:

- 최근 run 수
- 실패 run 수
- 작업 유형 필터
- mode 필터

### 3.2 Main Board

역할:

- task와 run의 현재 상태를 한눈에 보여주는 메인 작업 영역

초기 3개 컬럼:

- `Queue`
- `Debate Stream`
- `Synthesis`

상태 매핑:

- `Queue`: `draft`, `planned`
- `Debate Stream`: `running`, `revising`, `awaiting_review`
- `Synthesis`: `completed`, `failed`, `cancelled`

보드의 목적은 단순 drag target이 아니라 task와 run의 진행 단계 그룹을 표현하는 것이다.

### 3.3 Detail Panel

현재 구현에는 없지만 MVP에 필요한 다음 단계 영역이다.

역할:

- 선택된 task의 목표와 제약 표시
- 최신 run 상태 표시
- step 타임라인 표시
- artifact 목록 및 선택 표시
- verdict 및 추천 액션 표시

초기에는 우측 슬라이드 패널 또는 모달 형태로 시작할 수 있다.

## 4. 정보 구조

프런트엔드는 최소한 아래 객체를 이해하고 렌더링해야 한다.

### 4.1 Task

사용자가 해결하려는 문제 단위다.

표현 규칙:

- 보드 카드는 `task` 기준으로 1개만 렌더링한다.
- 카드에 표시되는 상태와 요약은 `latestRun` 기준으로 계산한다.
- 과거 run은 카드에 펼치지 않고 상세 패널에서 조회한다.

예시 필드:

```json
{
  "id": "task_123",
  "title": "FastAPI 에러 원인 분석",
  "type": "debugging",
  "goal": "500 에러 재현 및 원인 파악",
  "constraints": ["프로덕션 동작 변경 금지"],
  "priority": "high",
  "latestRunId": "run_001",
  "latestRunStatus": "running",
  "createdAt": "2026-04-18T10:00:00Z"
}
```

### 4.2 Run

task에 대한 실제 orchestration 실행 단위다.

```json
{
  "id": "run_001",
  "taskId": "task_123",
  "mode": "plan-execute-eval",
  "status": "running",
  "startedAt": "2026-04-18T10:05:00Z",
  "endedAt": null,
  "selectedArtifactId": null
}
```

### 4.3 Step

run 내부의 단계 정보다.

```json
{
  "id": "step_001",
  "runId": "run_001",
  "phase": "plan",
  "agentId": "agent_planner",
  "status": "completed",
  "summary": "원인 가설 3개와 점검 순서 제시"
}
```

### 4.4 Artifact

문서, 코드, 테스트, 로그 요약 같은 산출물이다.

```json
{
  "id": "artifact_001",
  "runId": "run_001",
  "type": "document",
  "title": "디버깅 분석 메모",
  "path": "doc/debug-note.md",
  "createdAt": "2026-04-18T10:08:00Z"
}
```

### 4.5 Verdict

평가 결과와 다음 액션 제안이다.

```json
{
  "id": "verdict_001",
  "runId": "run_001",
  "decision": "revise",
  "reason": "재현은 되었지만 회귀 테스트가 없음",
  "risks": ["테스트 부재", "원인 추정 근거 약함"],
  "recommendedNextAction": "retry_with_critique"
}
```

## 5. 카드 표현 규격

보드의 기본 카드 단위는 `Task summary + latest run snapshot` 조합이어야 한다.

즉, 하나의 task가 여러 번 재실행되어도 보드에 카드가 여러 장 생기지 않는다.

### 5.1 카드 최소 표시 항목

- task title
- task type
- latest run status
- primary agent role 또는 현재 phase
- 최신 요약 문장
- task id 또는 run id 식별자

### 5.2 카드 선택 표시 항목

- verdict badge
- artifact count
- retry count
- failure reason summary

### 5.3 역할 표현 규칙

- Planner: `primary`
- Executor 또는 Cline executor: `secondary`
- Evaluator: `tertiary`

역할은 색상만으로 표현하지 않고 텍스트 라벨도 함께 보여줘야 한다.

## 6. 작업 생성 UX

현재는 제목만 입력하는 단순 모달이지만, 제품 요구 기준으로는 아래 필드가 필요하다.

### 6.1 필수 입력

- `title`
- `type`
- `goal`

### 6.2 선택 입력

- `constraints`
- `priority`
- `orchestration mode`
- 관련 파일 또는 문서 경로

### 6.3 기본값

- orchestration mode 기본값은 `Planner -> Executor -> Evaluator`
- priority 기본값은 `medium`

## 7. 상태 모델과 보드 매핑

프런트는 내부 상태와 보드 표현 상태를 분리해서 관리해야 한다.

### 7.1 Run 상태 enum

- `draft`
- `planned`
- `running`
- `awaiting_review`
- `revising`
- `completed`
- `failed`
- `cancelled`

### 7.2 보드 컬럼 매핑

| Board Column | Run Status |
| :--- | :--- |
| `Queue` | `draft`, `planned` |
| `Debate Stream` | `running`, `awaiting_review`, `revising` |
| `Synthesis` | `completed`, `failed`, `cancelled` |

컬럼 배치 규칙:

- 카드 위치는 `task.latestRunStatus`를 기준으로 결정한다.
- `task` 자체의 생성 시점이나 기본 속성은 컬럼 배치를 직접 결정하지 않는다.

### 7.3 Drag and Drop 규칙

현재 구현은 자유 Drag & Drop이지만, 제품 기준에서는 무제한 상태 이동을 허용하면 안 된다.

초기 규칙:

- `Queue -> Debate Stream` 이동은 실행 시작 의미로 허용
- `Debate Stream -> Synthesis` 이동은 완료 또는 실패 확정 의미로 제한
- `Synthesis -> Queue` 이동은 직접 드래그가 아니라 `retry` 액션으로 처리

즉, 장기적으로는 Drag & Drop보다 명시적 action 버튼 중심으로 전환하는 것이 맞다.

## 8. API 계약 방향

초기 MVP에서 프런트가 의존하는 핵심 API 자원은 다음과 같다.

- `tasks`
- `runs`
- `steps`
- `artifacts`
- `verdicts`

### 8.1 Task 목록 조회

- **Endpoint**: `GET /api/tasks`
- **Purpose**: 보드의 카드 목록을 가져온다.

응답 예시:

```json
[
  {
    "id": "task_123",
    "title": "PRD 초안 작성",
    "type": "prd_generation",
    "goal": "기존 문서 분석 후 상위 PRD 작성",
    "priority": "medium",
    "latestRun": {
      "id": "run_001",
      "status": "awaiting_review",
      "mode": "plan-execute-eval",
      "currentPhase": "eval"
    }
  }
]
```

### 8.2 Task 생성

- **Endpoint**: `POST /api/tasks`
- **Purpose**: 새 task를 생성한다.

요청 예시:

```json
{
  "title": "테스트 케이스 보강",
  "type": "test_writing",
  "goal": "service 레이어 누락 테스트 추가",
  "constraints": ["snapshot 테스트 제외"],
  "priority": "medium",
  "mode": "plan-execute-eval"
}
```

### 8.3 Run 목록 또는 상세 조회

- **Endpoint**: `GET /api/tasks/{taskId}/runs`
- **Purpose**: 특정 task의 run 목록과 최신 상태를 조회한다.

### 8.4 Run 단건 조회

- **Endpoint**: `GET /api/runs/{runId}`
- **Purpose**: 선택한 run의 세부 상태와 메타데이터를 조회한다.

### 8.5 Run 생성

- **Endpoint**: `POST /api/tasks/{taskId}/runs`
- **Purpose**: 선택한 task를 새로 실행하거나 retry한다.

### 8.6 Artifact 조회

- **Endpoint**: `GET /api/runs/{runId}/artifacts`
- **Purpose**: 선택한 run의 산출물을 보여준다.

### 8.7 Verdict 조회

- **Endpoint**: `GET /api/runs/{runId}/verdict`
- **Purpose**: 평가 결과와 권장 액션을 가져온다.

### 8.8 Run 상태 업데이트 및 액션

- **Endpoint**: `PATCH /api/runs/{runId}`
- **Purpose**: 승인, 종료, 재검토 요청 같은 run 단위 상태 전이를 처리한다.

요청 예시:

```json
{
  "action": "approve"
}
```

경로 원칙:

- 목록 조회는 상위 리소스 아래에 둔다.
- 단건 조회는 해당 리소스 식별자를 직접 사용한다.
- 상태 전이는 `task`가 아니라 `run` 단위로 처리한다.

## 9. 프런트 상태 관리 규칙

현재 `taskState.tasks` 수준의 단순 구조는 MVP 시작점으로만 사용한다.

프런트 상태는 장기적으로 최소 아래 레벨로 나뉘어야 한다.

- `tasks`
- `selectedTaskId`
- `runsByTaskId`
- `artifactsByRunId`
- `verdictsByRunId`
- `ui.loading`
- `ui.error`

### 9.1 기본 로드 순서

1. 앱 시작
2. `GET /api/tasks`
3. 기본 선택 task 결정
4. 선택 task에 대해 `runs`, `artifacts`, `verdicts` 조회

### 9.2 갱신 전략

초기 MVP:

- 수동 새로고침 또는 주기적 polling

후속 단계:

- SSE 또는 WebSocket

## 10. 빈 상태, 로딩, 에러 상태

### 10.1 빈 상태

- task가 하나도 없으면 보드 전체에 작업 생성 가이드를 보여준다.
- 선택 task에 run이 없으면 실행 시작 CTA를 보여준다.
- run에는 artifact가 없고 완료되지 않았다면 대기 상태를 보여준다.

### 10.2 로딩 상태

- 보드 초기 로드 시 skeleton 또는 placeholder를 보여준다.
- detail panel 로드 시 section 단위 loading state를 둔다.

### 10.3 에러 상태

- task 목록 실패
- run 상세 실패
- artifact 조회 실패
- verdict 조회 실패
- 상태 변경 실패

각 에러는 최소한 다음을 제공해야 한다.

- 실패 위치
- 짧은 설명
- 재시도 action

## 11. 상세 패널 규격

상세 패널은 최소 아래 섹션을 가져야 한다.

### 11.1 Task Summary

- title
- type
- goal
- constraints
- priority

### 11.2 Run Timeline

- phase 목록
- agent 역할
- 단계 상태
- 단계별 summary

### 11.3 Artifact Viewer

- artifact type badge
- title
- path 또는 preview
- 선택/채택 상태

### 11.4 Verdict Panel

- decision
- reason
- risks
- recommended next action

### 11.5 Action Area

- retry
- approve
- reopen
- open artifact

액션 소유 규칙:

- `retry`, `approve`, `reopen`은 모두 `run` 액션이다.
- 새 retry는 기존 task 아래 새 run을 만드는 방식으로 동작한다.

## 12. 현재 구현과의 차이

현재 `static/` 구현은 아래 성격을 가진다.

- `index.html`: sidebar + 3컬럼 보드의 정적 레이아웃
- `app.js`: 로컬 mock task 배열 기반 렌더링
- drag and drop 중심 상호작용
- task 상세 패널 없음
- run, artifact, verdict 개념 없음

즉, 현재 구현은 제품의 최종 구조가 아니라 시각 목업의 첫 단계다.

## 13. 구현 우선순위

프런트는 아래 순서로 확장하는 것이 적절하다.

1. 현재 카드 데이터를 `task + latestRun` 구조로 재정의
2. 상태 enum을 `draft/planned/running/...` 구조로 교체
3. task 생성 모달에 `type`, `goal`, `mode` 추가
4. task 선택과 detail panel 추가
5. `GET /api/tasks` 연동
6. `runs`, `artifacts`, `verdicts` 조회 추가
7. retry/approve 같은 action 버튼 도입
8. drag and drop 의존도 축소

## 14. 수동 검증 기준

프런트 구현 후 최소 아래 항목을 검증해야 한다.

1. 앱 최초 진입 시 task 목록이 정상 렌더링된다.
2. 각 카드에서 task type과 latest run status가 함께 보인다.
3. task 선택 시 상세 패널에 run, artifact, verdict 정보가 표시된다.
4. 새 task 생성 시 필수 필드 검증이 동작한다.
5. 상태 변경 실패 시 사용자에게 에러가 보인다.
6. 빈 상태와 로딩 상태가 각각 구분되어 표시된다.

## 15. 관련 문서

- 제품 정의: `doc/PRODUCT-PRD.md`
- 프런트 구현 운영: `doc/FRONTEND-DELIVERY-PLAN.md`
- 디자인 레퍼런스: `doc/DESIGN.md`
