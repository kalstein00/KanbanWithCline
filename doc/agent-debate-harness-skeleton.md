# Define the content for the markdown file
md_content = """# Multi-Agent Debate Harness (Cline CLI 기반)

## 1. 개요
- **목적**: Cline CLI를 활용하여 에이전트 간 토론 과정을 자동화하고, 작업의 완성도를 높이는 Harness 구축
- **핵심 아키텍처**: Plan -> Execute -> Eval (Feedback Loop)

## 2. 에이전트 역할 정의
1. **Planner (설계자)**:
   - 목표 분석 및 세부 실행 계획(Task List) 수립
   - 제약 사항 및 성공 조건(Acceptance Criteria) 정의
2. **Executor (수행자)**:
   - Cline CLI를 통해 실제 코드 작성 및 명령어 실행
   - 실행 로그 및 결과물 생성
3. **Evaluator (평가자)**:
   - 실행 결과가 성공 조건을 만족하는지 검토
   - 에이전트 간 토론(Debate)을 통해 개선점 도출 및 피드백 생성

## 3. 워크플로우 (The Loop)
1. **[Phase: Plan]** 사용자 요구사항으로부터 작업 명세서 생성
2. **[Phase: Execute]** 계획에 따른 작업 수행
3. **[Phase: Eval]** 결과물 평가 및 토론 발생
   - Pass: 작업 종료
   - Fail: 피드백을 포함하여 **Phase: Plan**으로 회귀

## 4. 기술 스택 (예정)
- **CLI**: Cline CLI
- **Orchestrator**: Python (subprocess/typer) 또는 Shell Script
- **Storage**: Markdown 기반 로그 및 컨텍스트 관리
