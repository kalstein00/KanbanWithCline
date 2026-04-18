# Product PRD: Developer Agent Orchestration Workbench

## 1. 문서 목적

이 문서는 개발자가 `Cline`을 포함한 여러 agent를 오케스트레이션해 더 나은 결과물을 만들 수 있도록 돕는 제품의 상위 PRD다.

이 PRD는 다음 질문에 답하는 것을 목표로 한다.

- 누구를 위한 제품인가
- 어떤 문제를 해결하는가
- 어떤 작업을 지원해야 하는가
- 어떤 핵심 객체와 상태를 가져야 하는가
- 프런트엔드는 무엇을 보여줘야 하는가

구현 운영 방식은 별도 문서인 `doc/FRONTEND-DELIVERY-PLAN.md`에서 다룬다.

## 2. 제품 비전

이 제품은 단순한 칸반 보드가 아니라, 개발자가 다양한 작업을 agent에게 위임하고 그 과정을 추적하고 결과를 선택할 수 있는 `Agent Orchestration Workbench`다.

핵심 가치는 자동화 자체가 아니라 다음 두 가지다.

- 더 좋은 결과를 더 일관되게 얻는 것
- 중간 과정과 판단 근거를 추적 가능하게 만드는 것

## 3. 타깃 사용자

### Primary User

- AI 도구를 이미 활용하는 개발자
- 코드 작성, 디버깅, 테스트 작성, 문서화 작업을 자주 수행하는 개발자
- 단일 agent의 즉답보다 더 높은 품질과 검토 가능성을 원하는 사용자

### Secondary User

- 기술 리드 또는 리뷰어
- 작업 흐름과 산출물의 근거를 빠르게 파악해야 하는 사용자

## 4. 해결하려는 문제

개발자는 이미 다양한 agent 도구를 사용할 수 있지만, 다음 문제가 남아 있다.

- 단일 agent의 답변이 작업 종류에 따라 품질 편차가 크다.
- 계획, 실행, 평가가 한 덩어리로 섞여 결과 검증이 어렵다.
- 디버깅, PRD 작성, 테스트 작성 같은 작업은 서로 다른 사고 방식이 필요하다.
- 여러 관점의 결과를 비교하고 채택하는 흐름이 부족하다.
- 산출물은 남지만 왜 그런 결론이 나왔는지 추적하기 어렵다.

이 제품은 이를 해결하기 위해 task를 agent 기반 실행 단위로 분해하고, 각 실행의 계획, 결과, 평가를 시각적으로 관리한다.

## 5. 제품 목표

### 5.1 사용자 목표

- 개발자는 작업 유형에 맞는 agent orchestration을 선택할 수 있어야 한다.
- 개발자는 실행 과정과 중간 산출물을 확인할 수 있어야 한다.
- 개발자는 여러 결과를 비교하고 최종 결과를 채택하거나 재실행할 수 있어야 한다.

### 5.2 제품 목표

- 단일 agent 사용보다 더 일관된 품질의 산출물을 만든다.
- 작업 히스토리, 산출물, 평가 근거를 구조적으로 남긴다.
- 다양한 개발 작업 유형에 재사용 가능한 orchestration 패턴을 제공한다.

## 6. 핵심 사용 시나리오

### Scenario A. 문서 분석 후 PRD 생성

1. 사용자가 코드베이스 또는 문서 묶음을 입력한다.
2. Planner agent가 요구사항, 제약, 문서 범위, 작성 계획을 정리한다.
3. Reviewer가 계획의 누락, 모호성, 실행 가능성을 검토한다.
4. 승인된 계획만 Executor 또는 Cline으로 전달되어 초안 PRD를 작성한다.
5. Reviewer가 초안의 구조 결손, 요구사항 누락, 모호성을 검토한다.
6. Evaluator가 현재 run을 채택할지, 실행만 재시도할지, 계획부터 다시 시작할지 결정한다.
7. 사용자가 최종 PRD를 승인하거나 다음 루프를 시작한다.

### Scenario B. 디버깅

1. 사용자가 에러 로그와 관련 파일을 task로 등록한다.
2. Planner가 원인 가설, 점검 순서, 검증 계획을 제시한다.
3. Reviewer가 가설의 타당성, 점검 순서, 재현 전략의 누락 여부를 검토한다.
4. 승인된 계획을 기반으로 Executor가 재현, 수정, 검증을 시도한다.
5. Reviewer가 수정의 타당성, 회귀 위험, 검증 증거를 검토한다.
6. Evaluator가 실행 결과를 채택할지, 실행만 다시 할지, 계획을 수정해야 하는지 결정한다.
7. 사용자가 패치 또는 권장 조치를 채택한다.

### Scenario C. 테스트 케이스 작성

1. 사용자가 특정 모듈과 테스트 공백을 입력한다.
2. Planner가 테스트 전략, 경계 조건, 커버리지 목표를 정리한다.
3. Reviewer가 테스트 계획의 누락 케이스와 범위 적절성을 검토한다.
4. 승인된 계획을 기반으로 Executor가 테스트 코드를 작성한다.
5. Reviewer가 정상 경로, 경계 조건, flaky 가능성, 누락 케이스를 검토한다.
6. Evaluator가 결과를 채택할지, 실행 보강이 필요한지, 계획 재작성부터 필요한지 결정한다.
7. 사용자가 테스트 세트를 승인하거나 보강 요청한다.

## 7. 지원 작업 범위

초기 MVP는 다음 작업 유형을 지원한다.

- 문서 분석
- PRD 작성
- 디버깅
- 테스트 작성
- 코드 리뷰 보조
- 리팩터 계획 수립

후속 단계에서 고려할 작업은 다음과 같다.

- 성능 분석
- 보안 점검
- 마이그레이션 계획
- 릴리즈 노트 생성

## 8. 핵심 도메인 모델

### Task

사용자가 해결하려는 문제 단위다.

관계 규칙:

- 하나의 `task`는 여러 `run`을 가질 수 있다.
- 보드 카드는 기본적으로 `task` 단위로 1개만 노출한다.
- 카드의 현재 상태와 요약은 항상 `latestRun` 기준으로 계산한다.
- 재실행은 새로운 `run`을 만드는 방식으로 처리한다.

예시 필드:

- `id`
- `title`
- `type`
- `goal`
- `constraints`
- `priority`
- `latestRunId`
- `latestRunStatus`
- `createdAt`
- `createdBy`

### Agent

실행에 참여하는 역할 또는 도구 단위다.

역할 예시:

- `Planner`: 작업 계획과 성공 기준 정의
- `Reviewer`: 계획 또는 실행 산출물의 중간 검증
- `Executor`: 산출물 생성, 수정, 실행
- `Evaluator`: 전체 run 기준 최종 판단과 다음 루프 결정
- `Cline`: Executor 역할을 수행할 수 있는 구체적 agent 구현

예시 필드:

- `id`
- `name`
- `role`
- `provider`
- `capabilities`

### Run

특정 task에 대한 한 번의 orchestration 실행 세션이다.

관계 규칙:

- 각 `run`은 정확히 하나의 `task`에 속한다.
- 사용자의 승인, 재실행, 실패 복구는 기본적으로 `run` 단위 액션이다.
- `task`는 문제 정의를 유지하고, `run`이 실제 시도와 결과를 표현한다.

예시 필드:

- `id`
- `taskId`
- `mode`
- `status`
- `startedAt`
- `endedAt`
- `selectedArtifactId`

### Step

Run 내부의 세부 실행 단계다.

예시 필드:

- `id`
- `runId`
- `phase`
- `agentId`
- `status`
- `summary`

### Artifact

문서, 코드 패치, 테스트 결과, 로그 요약 같은 산출물이다.

예시 필드:

- `id`
- `runId`
- `type`
- `title`
- `content`
- `path`
- `createdAt`

### Verdict

평가 결과와 다음 액션 제안이다.

예시 필드:

- `id`
- `runId`
- `decision`
- `reason`
- `risks`
- `recommendedNextAction`
- `loopTarget`
- `approvalStatus`

## 9. Orchestration 모드

### Mode 1. Single Agent

- 빠른 탐색이나 단순 작업에 사용한다.
- 하나의 agent가 계획부터 실행까지 처리한다.

### Mode 2. Planner -> Reviewer -> Executor -> Reviewer -> Evaluator

- 기본 권장 모드다.
- 계획 검증과 실행 검증을 분리해 품질과 추적성을 확보한다.
- Reviewer는 phase에 따라 `plan review`와 `execution review`를 수행한다.

### Mode 3. Debate

- 둘 이상의 실행 관점이 필요할 때 사용한다.
- 복수 agent 결과를 비교하고 evaluator가 종합 의견을 낸다.

### Mode 4. Retry With Critique

- 첫 결과가 미흡할 때 Reviewer와 Evaluator의 피드백을 바탕으로 재실행한다.
- Evaluator는 `replan` 또는 `re-execute` 중 어디로 되돌릴지 결정한다.

### Mode 5. Human In The Loop

- 사용자 승인이 필요한 단계에서 수동 검토를 삽입한다.

## 10. 상태 모델

`todo / in-progress / done`만으로는 제품 상태를 설명하기 부족하다. MVP 기준의 run 상태는 다음과 같이 정의한다.

- `draft`
- `planning`
- `plan_review`
- `executing`
- `execution_review`
- `evaluating`
- `revising_plan`
- `revising_execution`
- `completed`
- `failed`
- `cancelled`

프런트의 3개 컬럼은 초기에는 아래와 같이 해석할 수 있다.

- `Queue`: `draft`, `planning`, `plan_review`
- `Debate Stream`: `executing`, `execution_review`, `evaluating`, `revising_plan`, `revising_execution`
- `Synthesis`: `completed`, `failed`, `cancelled`

보드 배치 규칙:

- 컬럼 배치는 `task.latestRunStatus` 기준으로 결정한다.
- `run` 히스토리는 상세 패널 또는 별도 타임라인에서 본다.
- 즉, 보드는 `task list`, 상세 패널은 `run history`를 담당한다.

## 11. 핵심 기능 요구사항

### FR-1. Task 생성

- 사용자는 다양한 작업 유형의 task를 생성할 수 있어야 한다.
- task는 최소한 제목, 작업 유형, 목표를 가져야 한다.

### FR-2. Orchestration 모드 선택

- 사용자는 task 실행 전 orchestration 모드를 선택할 수 있어야 한다.
- 기본값은 `Planner -> Reviewer -> Executor -> Reviewer -> Evaluator`로 한다.

### FR-3. Run 추적

- 사용자는 현재 실행 중인 run의 상태를 확인할 수 있어야 한다.
- 각 단계에서 어떤 agent가 무엇을 수행 중인지 요약이 보여야 한다.
- 시스템은 `plan review`와 `execution review`를 구분해 보여줘야 한다.

### FR-4. Artifact 확인

- 사용자는 run별 산출물을 확인할 수 있어야 한다.
- 산출물은 문서, 코드, 테스트, 로그 중 무엇인지 구분되어야 한다.

### FR-5. Verdict 확인

- 사용자는 평가 결과와 리스크를 확인할 수 있어야 한다.
- 시스템은 `채택`, `실행 재시도`, `계획 재작성`, `보완 필요` 같은 다음 액션을 제안해야 한다.

### FR-6. 재실행

- 사용자는 이전 평가 피드백을 바탕으로 동일 task를 다시 실행할 수 있어야 한다.
- 재실행은 기존 task를 수정하는 것이 아니라 새 run을 생성해야 한다.
- 시스템은 재실행 시 `Executor` 단계부터 재시도할지 `Planner` 단계부터 다시 시작할지 구분해야 한다.

### FR-7. 히스토리 확인

- 사용자는 과거 run과 선택된 산출물을 다시 열람할 수 있어야 한다.

## 12. 프런트엔드 요구사항

프런트는 단순 보드가 아니라 orchestration 상태를 보여주는 워크벤치여야 한다.

### UI-1. Task 중심 보드

- 현재 task와 run 상태를 한눈에 보여줘야 한다.
- 컬럼은 단순 장식이 아니라 상태 그룹을 표현해야 한다.

### UI-2. Run 상세 패널

- 선택한 카드의 상세 실행 단계, agent, artifact, verdict를 볼 수 있어야 한다.
- 계획 검토와 실행 검토가 어떤 근거로 통과 또는 반려되었는지 볼 수 있어야 한다.

### UI-3. Agent 가시성

- Planner, Reviewer, Executor, Evaluator, Cline 같은 agent의 역할을 명확히 구분해야 한다.

### UI-4. 결과 비교

- Debate 또는 재실행 시 결과 비교가 가능해야 한다.

### UI-5. 실패 가시성

- 실패 원인과 다음 조치를 사용자가 즉시 이해할 수 있어야 한다.

## 13. API 및 데이터 계약 방향

초기 API는 단순하게 시작하되, 장기적으로는 아래 자원을 기준으로 설계한다.

- `tasks`
- `runs`
- `steps`
- `artifacts`
- `verdicts`
- `agents`

초기 MVP에서 프런트에 반드시 필요한 최소 API는 다음과 같다.

- `GET /api/tasks`
- `POST /api/tasks`
- `GET /api/tasks/{taskId}/runs`
- `POST /api/tasks/{taskId}/runs`
- `GET /api/runs/{runId}`
- `PATCH /api/runs/{runId}`
- `GET /api/runs/{runId}/artifacts`
- `GET /api/runs/{runId}/verdict`

경로 원칙:

- 컬렉션 조회는 상위 리소스 아래에 둔다.
- 단건 조회는 해당 리소스의 식별자를 직접 사용한다.
- 상태 전이와 승인 같은 실행 제어는 `task`가 아니라 `run` 단위로 처리한다.

## 14. 비기능 요구사항

### NFR-1. 추적성

- 각 run은 어떤 입력과 어떤 결과를 거쳐 결론에 도달했는지 추적 가능해야 한다.
- 특히 계획 검토와 실행 검토의 승인 또는 반려 근거가 분리되어 남아야 한다.

### NFR-2. 검토 가능성

- 사용자는 자동 생성 결과를 그대로 믿지 않고 검토할 수 있어야 한다.

### NFR-3. 단순한 초기 스택

- 초기 구현은 FastAPI + 정적 프런트 구조를 유지해 빠르게 검증한다.

### NFR-4. 작업 유형 확장성

- 문서 작업에서 출발하더라도 디버깅, 테스트 작성 등으로 자연스럽게 확장 가능해야 한다.

### NFR-5. 실패 복원력

- 실행 실패가 전체 세션 손실로 이어지지 않아야 한다.

## 15. 작업 유형별 완료 기준

작업 유형이 넓기 때문에 reviewer와 evaluator가 주관적 메모로 끝나지 않도록 최소 완료 기준을 둔다.

### Type A. 문서 분석

- 핵심 문서 범위가 명시되어야 한다.
- 주요 요구사항, 제약, 오픈 이슈가 분리되어야 한다.
- 결과 산출물은 재검토 가능한 구조를 가져야 한다.

### Type B. PRD 작성

- 목표, 사용자, 범위, 핵심 기능, 비기능 요구사항이 포함되어야 한다.
- 누락된 결정 사항은 오픈 이슈로 분리되어야 한다.
- reviewer는 계획 또는 결과의 모호성, 결손 섹션, 범위 누락을 지적해야 한다.
- evaluator는 채택 또는 재루프 판단 근거를 제시해야 한다.

### Type C. 디버깅

- 재현 여부가 명시되어야 한다.
- 원인 가설 또는 확정 원인이 기록되어야 한다.
- 수정안 또는 권장 조치와 회귀 위험이 함께 제시되어야 한다.

### Type D. 테스트 작성

- 대상 모듈과 커버하려는 케이스 범위가 명시되어야 한다.
- 정상 경로와 경계/실패 케이스가 구분되어야 한다.
- flaky 가능성 또는 누락 케이스가 review에 포함되어야 한다.

### Type E. 코드 리뷰 보조

- 주요 리스크가 심각도와 함께 정리되어야 한다.
- 단순 요약과 actionable issue가 구분되어야 한다.
- 승인 가능 여부 또는 추가 확인 필요 항목이 제시되어야 한다.

## 16. 성공 지표

MVP 단계에서는 아래 지표를 본다.

- 첫 결과 도출 시간
- 사용자 승인까지 걸린 시간
- 재실행 횟수
- 최종 산출물 채택률
- 디버깅/테스트/문서 작업별 만족도

## 17. MVP 범위

초기 MVP는 다음 범위에 집중한다.

- 개발자 단일 사용자
- Task 생성
- 기본 orchestration 모드 선택
- 3개 컬럼 기반 상태 보드
- run 진행 상태 시각화
- artifact와 verdict 표시
- plan review와 execution review 분리 표시
- 수동 재실행

MVP에서 제외한다.

- 실시간 다중 사용자 협업
- 복잡한 권한 체계
- 외부 에이전트 마켓플레이스
- 고급 통계 대시보드

## 18. 오픈 이슈

아래 항목은 후속 설계에서 확정해야 한다.

- Cline을 기본 Executor로 고정할지, 범용 agent 중 하나로 둘지
- run 갱신 방식을 polling으로 시작할지, SSE/WebSocket으로 갈지
- artifact diff를 어떤 수준까지 UI에서 보여줄지
- human approval 단계를 `plan review`, `execution review`, `evaluation` 중 어디에 삽입할지
- task type별 템플릿을 둘지
- Reviewer를 단일 role의 두 모드로 구현할지, plan/execution reviewer를 분리된 agent로 둘지

용어 정리 필요:

- 현재 문서에서는 `Cline`을 기본적으로 `Executor` 역할을 수행하는 agent로 가정한다.
- 다만 향후에는 다른 executor agent와 병렬 비교될 수 있으므로, 제품 모델상으로는 `Agent`의 한 종류로 유지한다.
- `Reviewer`는 계획 단계와 실행 단계 모두에 적용되는 검증 role이며, phase에 따라 다른 체크리스트를 사용한다.
- `Evaluator`는 결함 탐지보다 `채택 / re-execute / replan` 결정을 내리는 orchestration 판단자다.

## 19. 다음 문서 작업

이 PRD를 기준으로 바로 이어서 정리할 문서는 다음과 같다.

1. `doc/FRONTEND.md`
   task, run, artifact, verdict를 화면에 어떻게 표현할지 구체화
2. `doc/FRONTEND-DELIVERY-PLAN.md`
   현재 정적 프런트를 제품 PRD에 맞춰 어떤 순서로 구현할지 정리
3. 백엔드 API 초안 문서
   task/run/step/artifact/verdict 중심 REST 계약 정의
