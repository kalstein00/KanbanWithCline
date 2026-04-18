# Frontend Delivery Plan: Cline CLI Operating Model

## 1. 문서 목적

이 문서는 `doc/PRODUCT-PRD.md`와 `doc/FRONTEND.md`를 기준으로, 현재 정적 프런트를 제품 구조에 맞게 확장하기 위한 실행 계획 문서다.

기준 자산은 다음과 같다.

- `doc/PRODUCT-PRD.md`
- `doc/FRONTEND.md`
- `doc/DESIGN.md`
- `static/index.html`
- `static/app.js`
- `static/styles.css`

이 문서는 제품 요구사항 문서가 아니라, `Cline CLI`를 이용해 어떤 순서와 단위로 프런트 작업을 진행할지 정의한다.

## 2. 현재 상태 요약

현재 프런트엔드는 다음 수준까지 준비되어 있다.

- 3개 컬럼 기반 칸반 레이아웃이 존재한다.
- 로컬 mock state 기반 카드 렌더링이 구현되어 있다.
- 모달 기반 task 추가와 Drag & Drop이 구현되어 있다.
- 상세 패널, run 히스토리, artifact, verdict 개념은 아직 없다.

현재 구현의 핵심 한계는 다음과 같다.

- 카드가 `task`와 `run`을 구분하지 못한다.
- 보드 상태가 `todo / in-progress / done` 수준에 머물러 있다.
- 실행 제어가 `run` 액션이 아니라 단순 카드 이동으로 표현되어 있다.

## 3. 목표 구현 상태

프런트는 다음 상태로 수렴해야 한다.

- 보드 카드는 `task` 단위로 1개만 보인다.
- 카드의 상태와 요약은 `latestRun` 기준으로 표시된다.
- 상세 패널에서 `run timeline`, `artifact`, `verdict`를 확인할 수 있다.
- `retry`, `approve`, `reopen`은 모두 `run` 액션으로 처리된다.
- API는 `task` 생성과 `run` 조회/실행/상태 전이를 분리한다.

## 4. Cline CLI 운영 원칙

`Cline CLI`는 아래 순서로 작업한다.

1. 최신 문서 문맥 읽기
2. 이번 작업의 수정 범위 확정
3. 최소 단위 구현
4. 수동 검증 또는 로컬 검증 수행
5. 문서와 구현 동기화

운영 규칙:

- 한 번의 작업에서 레이아웃 개편, 상태 모델 재설계, API 계약 변경을 동시에 하지 않는다.
- `task`와 `run`의 책임을 섞지 않는다.
- 구현 중 문서와 충돌이 생기면 문서 기준을 먼저 맞춘다.

## 5. 작업 단위 정의

### Unit A. Board Model

- `task + latestRun` 카드 구조 도입
- `latestRunStatus` 기반 컬럼 배치
- 기존 `todo / in-progress / done` 제거

완료 기준:

- 카드 렌더링 로직이 `task`와 `latestRun`을 함께 이해한다.

### Unit B. Task Creation

- task 생성 모달 확장
- `title`, `type`, `goal`, `mode` 입력 도입

완료 기준:

- 새 task가 제품 문서 기준 필수 필드를 만족한다.

### Unit C. Detail Panel

- 선택 task 표시
- run 목록 또는 최신 run 표시
- artifact/verdict 섹션 추가

완료 기준:

- 상세 패널 없이 제품 핵심 흐름이 막히지 않도록 최소 정보가 노출된다.

### Unit D. Run API Integration

- `GET /api/tasks`
- `GET /api/tasks/{taskId}/runs`
- `GET /api/runs/{runId}`
- `GET /api/runs/{runId}/artifacts`
- `GET /api/runs/{runId}/verdict`
- `POST /api/tasks/{taskId}/runs`
- `PATCH /api/runs/{runId}`

완료 기준:

- task 생성과 run 실행/상태 전이가 분리되어 동작한다.

### Unit E. UX Reliability

- loading
- empty
- error
- action pending

완료 기준:

- 네트워크 성공 가정만으로 동작하지 않는다.

## 6. 권장 구현 순서

1. 현재 카드 데이터 구조를 `task + latestRun` 모델로 교체
2. 보드 컬럼을 `draft/planned/running/...` 상태 모델에 맞게 변경
3. task 생성 모달에 `type`, `goal`, `mode` 추가
4. 선택 task와 detail panel 추가
5. `GET /api/tasks` 연동
6. `GET /api/tasks/{taskId}/runs`, `GET /api/runs/{runId}` 연동
7. `GET /api/runs/{runId}/artifacts`, `GET /api/runs/{runId}/verdict` 연동
8. `POST /api/tasks/{taskId}/runs`, `PATCH /api/runs/{runId}` 액션 연결
9. drag and drop 의존도 축소 및 명시적 action 버튼 전환
10. loading, empty, error 상태 보강

## 7. 프런트 작업 요구사항

### FR-1. Task 목록 조회

- 앱 시작 시 task 목록을 로드해야 한다.
- 각 카드는 task 요약과 latest run 상태를 함께 보여야 한다.

### FR-2. Task 생성

- 사용자는 모달에서 새 task를 생성할 수 있어야 한다.
- 생성 시 최소 `title`, `type`, `goal` 입력 검증이 동작해야 한다.

### FR-3. Run 조회

- 사용자는 선택된 task의 run 히스토리 또는 최신 run 상태를 볼 수 있어야 한다.

### FR-4. Run 액션

- 사용자는 `retry`, `approve`, `reopen` 같은 run 액션을 수행할 수 있어야 한다.
- 상태 전이는 `PATCH /api/runs/{runId}` 또는 `POST /api/tasks/{taskId}/runs`로 반영되어야 한다.

### FR-5. Artifact / Verdict 표시

- 사용자는 선택된 run의 artifact와 verdict를 확인할 수 있어야 한다.

## 8. 검증 항목

최소 검증 항목은 다음과 같다.

- 페이지가 정상 로드된다.
- 보드 카드가 `task + latestRun` 구조로 표시된다.
- 선택 task에 대한 상세 패널이 열린다.
- run 히스토리 또는 최신 run 정보가 보인다.
- retry/approve 같은 액션 실패 시 에러가 노출된다.
- 빈 상태와 로딩 상태가 각각 구분되어 표시된다.

## 9. Cline CLI 실행 템플릿

### 입력 템플릿

- 목표: 무엇을 바꿀 것인가
- 범위: 어떤 파일까지 수정 가능한가
- 제약: 건드리면 안 되는 영역은 무엇인가
- 완료 조건: 무엇이 되면 끝인가

### 실행 예시

```bash
cline "doc/PRODUCT-PRD.md와 doc/FRONTEND.md를 기준으로 static/app.js의 카드 모델을 task+latestRun 구조로 바꾸고, detail panel skeleton까지 추가해줘. 수동 검증 절차도 정리해."
```

### 결과 템플릿

- 수정 파일
- 사용자 영향
- 검증 결과
- 남은 리스크

## 10. 산출물 관리 원칙

- 제품 요구: `doc/PRODUCT-PRD.md`
- 구현 가이드: `doc/FRONTEND.md`
- 디자인 기준: `doc/DESIGN.md`
- 실제 구현: `static/`

운영 원칙:

- 구현이 문서를 바꾸면 관련 문서도 같은 흐름 안에서 갱신한다.
- 문서와 구현이 어긋난 상태를 장기간 방치하지 않는다.

## 11. 문서 수용 기준

이 실행 계획 기준으로 프런트 작업이 성공하려면 아래 조건을 만족해야 한다.

1. 작업 요청마다 목표, 범위, 완료 조건이 분리되어 정의된다.
2. 프런트 변경은 Board Model, Task Creation, Detail Panel, Run API, UX 중 어떤 단위인지 구분된다.
3. 구현 후 최소 검증 절차가 항상 수행된다.
4. `doc/FRONTEND.md`와 실제 구현의 불일치가 발견되면 후속 작업으로 관리된다.
5. 결과적으로 정적 목업이 run 중심 제품 UI로 단계적으로 전환된다.

## 12. 다음 권장 액션

가장 먼저 수행할 `Cline CLI` 작업은 다음 두 가지다.

1. `static/app.js`의 mock state를 `task + latestRun` 구조로 바꾸고 컬럼 매핑을 `latestRunStatus` 기준으로 교체
2. `static/index.html`에 detail panel skeleton을 추가해 run, artifact, verdict를 수용할 공간을 만든다
