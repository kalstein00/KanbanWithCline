# Product PRD: Skill Format Introduction

## 1. 문서 목적

이 문서는 agent가 반복 작업 중 축적한 재사용 지식을 `skill` 포맷으로 구조화해 저장, 검색, 주입, 갱신하는 기능의 제품 요구사항을 정의한다.

이 PRD는 다음 질문에 답하는 것을 목표로 한다.

- 왜 `memory.md` 대신 `skill` 포맷이 필요한가
- 어떤 형태의 지식을 `skill`로 다뤄야 하는가
- task 실행 시 어떤 방식으로 `skill`을 검색하고 주입해야 하는가
- 새로운 지식을 언제 어떤 규칙으로 `skill`로 승격해야 하는가
- 초기 MVP에서 어디까지 구현해야 하는가

## 2. 배경과 문제 정의

agent는 task를 반복하면서 저장소 규칙, 작업 절차, 실패 패턴, 리뷰 기준 같은 유의미한 지식을 학습할 수 있다. 그러나 이 지식이 매번 프롬프트 안에서 일회성으로 소비되면 다음 문제가 발생한다.

- 동일한 실수와 탐색 비용이 반복된다.
- repo 또는 팀에 특화된 운영 규칙이 누적되지 않는다.
- 긴 `memory.md`는 검색과 주입 단위가 거칠어 프롬프트 비대화를 유발한다.
- task history와 재사용 가능한 운영 지식이 섞여 관리가 어려워진다.
- 오래된 규칙과 검증되지 않은 경험이 분리되지 않아 오염 가능성이 커진다.

이 제품은 재사용 가치가 있는 지식을 atomic한 `skill` 문서로 분리하고, 헤더 메타데이터 검색 후 필요한 본문만 읽어 주입하는 방식으로 이를 해결한다.

## 3. 제품 비전

이 기능의 목표는 agent가 스스로 프롬프트를 무한히 늘리는 것이 아니라, 검토 가능하고 조합 가능한 `지식 캡슐`을 축적하는 것이다.

핵심 가치는 다음과 같다.

- task에 맞는 실행 맥락을 짧고 정확하게 주입한다.
- repo별, 팀별, 작업 유형별 운영 지식을 누적 가능하게 만든다.
- 사람이 읽고 수정할 수 있는 문서 기반 형식을 유지한다.
- 새로운 지식을 검증 가능한 흐름으로 승격해 메모리 오염을 줄인다.

## 4. 목표와 비목표

### 4.1 제품 목표

- 재사용 가능한 작업 지식을 `skill` 단위로 저장할 수 있어야 한다.
- task 시작 시 관련 `skill`만 선택적으로 읽어 프롬프트에 주입할 수 있어야 한다.
- task 종료 시 발견한 지식을 `candidate skill`로 기록하고, 검토 후 `validated skill`로 승격할 수 있어야 한다.
- 사용자는 어떤 `skill`이 어떤 task에 적용되었는지 추적할 수 있어야 한다.

### 4.2 비목표

- 초기 MVP에서 벡터 데이터베이스나 복잡한 임베딩 검색을 필수로 요구하지 않는다.
- 모든 task history를 자동으로 `skill`로 승격하지 않는다.
- agent가 사람 승인 없이 기존 `validated skill`을 임의로 덮어쓰는 자동 자가 수정은 지원하지 않는다.

## 5. 핵심 사용자

### Primary User

- 반복적인 개발 작업을 agent에 위임하는 개발자
- repo별 작업 규칙과 운영 노하우를 축적하고 싶은 사용자
- prompt engineering보다 문서 기반 운영을 선호하는 사용자

### Secondary User

- agent 실행 정책을 관리하는 기술 리드
- 팀 차원의 작업 규칙을 `skill`로 표준화하고 싶은 리뷰어 또는 운영자

## 6. 해결하려는 사용자 문제

- 사용자는 동일한 repo에서도 task마다 같은 설명을 반복해서 제공해야 한다.
- agent는 이전 task에서 배운 유용한 규칙을 안정적으로 재사용하지 못한다.
- 긴 메모리 문서는 읽기 어렵고 task 관련 부분만 선택적으로 가져오기 어렵다.
- 검증되지 않은 경험칙이 누적되면 agent 품질이 오히려 악화될 수 있다.

## 7. 제품 원칙

- `skill`은 atomic해야 한다. 하나의 문서는 한 가지 규칙, 절차, 휴리스틱 또는 문맥만 담당한다.
- 검색은 헤더 기반으로 먼저 수행하고, 본문은 후보가 선정된 후에만 읽는다.
- task 기록과 재사용 가능한 지식은 분리한다.
- 새 지식은 `raw note -> candidate -> validated` 승격 단계를 거친다.
- 사람이 읽고 수정 가능한 문서 포맷을 우선한다.

## 8. 핵심 사용 시나리오

### Scenario A. Repo 규칙 재사용

1. 사용자가 의존성 설치 관련 task를 생성한다.
2. 시스템은 `package manager`, `install`, `dependency`와 관련된 `skill` 헤더를 검색한다.
3. `pnpm 사용 규칙` skill이 선택된다.
4. 선택된 본문만 실행 프롬프트에 주입된다.
5. agent는 `npm` 대신 `pnpm`을 사용해 작업한다.

### Scenario B. 반복 실패 패턴 회피

1. 사용자가 flaky 테스트 수정 task를 실행한다.
2. 시스템은 테스트 관련 `anti-pattern` 또는 triage skill을 검색한다.
3. 재시도보다 원인 분리 우선이라는 skill이 주입된다.
4. agent는 잘못된 반복 재실행 대신 로그와 격리 전략을 우선 적용한다.

### Scenario C. 새로운 지식 승격

1. agent가 task 중 새로운 repo 규칙을 발견한다.
2. 종료 단계에서 해당 내용을 `candidate skill`로 기록한다.
3. 사용자 또는 평가 단계가 중복 여부, 범위, 정확성을 검토한다.
4. 승인된 항목만 `validated skill`로 저장되어 이후 검색 대상이 된다.

## 9. 기능 범위

초기 MVP는 다음 기능을 지원한다.

- `skill` 문서 포맷 정의
- 헤더 메타데이터 기반 검색
- 선택된 `skill` 본문 로드
- task별 사용 `skill` 추적
- `candidate skill` 생성 및 승인 후 승격

후속 단계에서 고려할 기능은 다음과 같다.

- 본문 내용 기반 랭킹 보정
- 벡터 검색 또는 하이브리드 검색
- 사용 빈도 기반 정렬
- 만료 또는 재검증 알림
- 충돌하는 `skill` 간 우선순위 정책 자동화

## 10. 정보 구조와 저장소 설계

### 10.1 디렉터리 구조

예시:

```text
skills/
  validated/
    repo/
    testing/
    review/
    coding/
  candidates/
  archive/
```

### 10.2 Skill 문서 포맷

모든 `skill`은 파싱 가능한 헤더와 자유 형식 본문을 가진다.

예시:

```md
---
name: repo-pnpm-rule
tags: [repo, build, package-manager]
scope: repo
triggers: [pnpm, install, dependency, build]
summary: 이 저장소에서는 npm 대신 pnpm을 사용한다.
kind: rule
confidence: high
status: validated
last_verified: 2026-04-18
---

# When to use
패키지 설치, 스크립트 실행, lockfile 수정 작업

# Guidance
- `npm install` 대신 `pnpm add`
- `package-lock.json` 생성 금지
- `pnpm-lock.yaml` 기준 유지

# Evidence
- repo 설정 파일
- 기존 CI 스크립트
```

### 10.3 필수 메타데이터

- `name`: 고유 식별자
- `summary`: 검색과 선택에 사용되는 1문장 요약
- `tags`: 주제 분류용 키워드
- `triggers`: task 입력과 매칭될 수 있는 키워드
- `scope`: `global`, `repo`, `task-type`, `team` 중 하나
- `kind`: `fact`, `rule`, `workflow`, `heuristic`, `anti-pattern` 중 하나
- `status`: `candidate`, `validated`, `archived`
- `confidence`: `low`, `medium`, `high`
- `last_verified`: 마지막 검증 날짜

### 10.4 선택 메타데이터

- `source_tasks`
- `owner`
- `priority`
- `related_skills`
- `expires_at`

## 11. 도메인 모델

### Skill

재사용 가능한 작업 지식 문서 단위다.

예시 필드:

- `id`
- `name`
- `path`
- `summary`
- `tags`
- `triggers`
- `scope`
- `kind`
- `status`
- `confidence`
- `lastVerified`

### SkillCandidate

task 종료 후 승격 전 상태의 지식 초안이다.

예시 필드:

- `id`
- `proposedContent`
- `sourceTaskId`
- `reason`
- `dedupeMatches`
- `reviewStatus`

### SkillSelection

특정 task 또는 run에 어떤 `skill`이 선택되어 주입되었는지 나타낸다.

예시 필드:

- `taskId`
- `runId`
- `skillId`
- `selectionReason`
- `rank`
- `appliedAt`

## 12. 사용자 흐름

### 12.1 Task 시작 시

1. 시스템은 task 제목, 설명, 유형에서 키워드를 추출한다.
2. `validated skill` 헤더를 대상으로 검색한다.
3. 관련도 점수를 계산해 상위 후보를 선택한다.
4. 상위 2개에서 5개 사이의 `skill`만 본문을 로드한다.
5. 본문 요약 또는 핵심 guidance를 실행 프롬프트에 삽입한다.

### 12.2 Task 종료 시

1. agent는 새로 발견한 지식이 있는지 요약한다.
2. 시스템은 기존 `skill`과의 중복 또는 충돌을 검사한다.
3. 재사용 가치가 있는 항목만 `candidate skill`로 저장한다.
4. 승인 또는 평가 단계를 통과한 후보만 `validated`로 승격한다.

## 13. 검색 및 선택 요구사항

### 13.1 검색 입력

- task title
- task description
- task type
- 최근 선택된 `skill`

### 13.2 랭킹 기준

- `triggers` 직접 매칭
- `tags` 매칭 수
- `summary` 텍스트 유사성
- `scope` 적합성
- `confidence`
- `last_verified` 최신성

### 13.3 선택 정책

- 기본적으로 상위 2개에서 5개 사이만 선택한다.
- 동일 의미의 중복 `skill`은 1개만 선택한다.
- `candidate` 상태는 기본 검색 대상에서 제외한다.
- 오래된 `skill`은 최신 검증 항목보다 낮은 우선순위를 가진다.

## 14. 승격 및 검증 정책

### 14.1 승격 조건

- 한 번 이상 명확한 증거와 함께 관찰되었거나
- 반복 task에서 재사용 가능성이 높고
- task history가 아닌 일반화된 규칙 또는 절차로 요약 가능해야 한다.

### 14.2 승격 금지 항목

- 특정 task에만 유효한 일회성 메모
- 근거가 없는 추정
- 사용자 승인 없이 행동 제약을 강제하는 규칙
- 기존 `validated skill`과 충돌하지만 해결되지 않은 후보

### 14.3 검증 주체

- 초기 MVP에서는 사용자 또는 evaluator 단계가 검증한다.
- 후속 단계에서 자동 검증 보조를 추가할 수 있다.

## 15. UI 및 운영 요구사항

- 사용자는 task 상세 화면에서 적용된 `skill` 목록을 볼 수 있어야 한다.
- 사용자는 각 `skill`의 요약, 상태, 마지막 검증 날짜를 확인할 수 있어야 한다.
- 사용자는 `candidate skill`을 검토, 수정, 승인, 보관할 수 있어야 한다.
- 사용자는 특정 `skill`을 수동 pin 하거나 제외할 수 있어야 한다.

## 16. 비기능 요구사항

- 검색은 헤더만 읽는 경량 경로를 기본으로 해야 한다.
- 본문 로드는 선택된 소수의 후보에 한정해야 한다.
- 포맷은 사람이 직접 수정 가능한 plain text 기반이어야 한다.
- 실패 시에도 `skill` 미적용 상태로 task 실행이 가능해야 한다.
- 잘못된 파싱이나 누락된 메타데이터가 있어도 전체 시스템이 중단되면 안 된다.

## 17. 성공 지표

- 동일 유형 task에서 반복 설명 입력량 감소
- repo 규칙 위반 빈도 감소
- 재실행 횟수 또는 초기 탐색 시간 감소
- 사용자가 승인한 `candidate -> validated` 전환율
- 적용된 `skill`에 대한 사용자 유지율 또는 재사용률

## 18. 리스크와 대응

### Risk 1. Skill 오염

검증되지 않은 경험칙이 누적되면 잘못된 행동을 강화할 수 있다.

대응:

- `candidate`와 `validated`를 분리한다.
- `confidence`와 `last_verified`를 강제한다.

### Risk 2. 과도한 분해

너무 작은 단위의 `skill`은 검색 비용과 조합 복잡도를 키운다.

대응:

- atomic 기준을 문서화한다.
- 중복 또는 지나친 세분화는 정기적으로 병합한다.

### Risk 3. 프롬프트 비대화 재발

후보를 너무 많이 선택하면 `memory.md`와 같은 문제가 재발한다.

대응:

- 상위 소수만 선택한다.
- 본문 전체 대신 핵심 guidance만 주입할 수 있게 한다.

### Risk 4. 지식 노후화

repo 정책이나 워크플로우가 바뀌면 오래된 `skill`이 오작동을 유발할 수 있다.

대응:

- `last_verified`와 `expires_at`를 운영한다.
- 오래된 항목은 자동으로 랭킹을 낮춘다.

## 19. 단계별 구현 제안

### Phase 1. 문서 포맷 도입

- `skills/validated`, `skills/candidates` 디렉터리 생성
- YAML 헤더 기반 포맷 정의
- 헤더 검색과 본문 선택 로드 구현

### Phase 2. 실행 연동

- task 시작 시 자동 검색 및 `skill` 선택
- run에 적용 `skill` 기록
- task 종료 시 `candidate skill` 생성

### Phase 3. 운영 강화

- 승인 UI 또는 검토 플로우 추가
- 중복 탐지 및 충돌 탐지 추가
- 최신성 및 사용 빈도 기반 랭킹 보정

## 20. MVP 수용 기준

- 시스템은 `validated skill` 헤더를 검색해 관련 후보를 찾을 수 있어야 한다.
- 시스템은 선택된 `skill`의 본문만 읽어 실행 컨텍스트에 주입할 수 있어야 한다.
- 시스템은 task 종료 시 새 지식을 `candidate skill` 문서로 저장할 수 있어야 한다.
- 사용자는 `candidate skill`을 검토 후 `validated`로 승격할 수 있어야 한다.
- 사용자는 특정 run에 어떤 `skill`이 적용되었는지 확인할 수 있어야 한다.

