# Multi-Agent Debate Harness Design Specification (Light Mode)

이 문서는 Stitch 프로젝트 "Multi-Agent Debate Harness"의 실제 시각적 결과물(Light Mode)을 바탕으로 정리된 디자인 사양입니다. 

## 프로젝트 정보
- **디자인 컨셉**: "The Orchestrator’s Lens" - 라이트 모드 기반의 에디토리얼 명령 센터

## 디자인 시스템 핵심 요약 (Light Mode)

### 1. 색상 팔레트
- **Background**: `#FFFFFF` (Pure White)
- **Primary (Planner)**: `#005AC2` (Deep Academic Blue)
- **Secondary (Executor)**: `#6B3D91` (Action Purple)
- **Tertiary (Evaluator)**: `#006A60` (Analytical Teal)
- **Surface Tiers**:
    - Structural: `#F8F9FA`
    - High Intensity: `#F0F2F5`
    - Interactive: `#E1E3E6`

### 2. 주요 디자인 규칙
- **No-Line Rule**: 테두리를 사용하지 않고, 배경의 명도 차이와 부드러운 그림자(Ambient Shadows)로 영역을 구분합니다.
- **Light Glassmorphism**: 화이트 톤의 반투명 배경(`rgba(255, 255, 255, 0.7)`)과 강력한 블러 효과를 사용하여 레이어 간의 깊이감을 표현합니다.
- **Typography (Inter)**: 다크 그레이(` #1A1C1E`) 텍스트를 사용하여 밝은 배경에서의 가독성을 극대화합니다.

### 3. 컴포넌트 스타일
- **카드(Cards)**: `border-radius: 24px` 적용, 공중에 떠 있는 듯한 플로팅 효과.
- **네스티드 플로트(Nested Float)**: 카드 내부에 에이전트의 사고 과정을 담는 더 어두운 회색 톤의 전용 영역 배치.

## 레퍼런스 화면
- **스크린샷**: `doc/screenshot.webp` (화이트 배경의 실제 레이아웃 참조)
