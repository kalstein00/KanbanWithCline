# 🏗️ Premium Kanban Web App

"The Orchestrator’s Lens" 디자인 시스템을 기반으로 한 프리미엄 칸반 보드 웹 애플리케이션입니다.
Glassmorphism, No-Line Policy, 그리고 감각적인 비대칭 레이아웃을 제공합니다.

---

## 🚀 시작하기

이 프로젝트는 파이썬 패키지 관리 도구로 `uv`를 사용합니다.

### 1. 필수 조건
- **Python**: 3.12 이상
- **uv**: 설치되어 있어야 함 ([uv 설치 가이드](https://github.com/astral-sh/uv))

### 2. 설치 및 준비
프로젝트 폴더에서 다음 명령어를 실행하여 종속성을 설치합니다.
```bash
uv sync
```

---

## 🏃 실행 방법

상황에 맞는 실행 명령어를 선택하세요. 모든 명령어는 호스트(`0.0.0.0`) 설정을 포함하고 있어 외부(Windows 등)에서도 접속 가능합니다.

### ✅ 개발 모드 (추천 - 자동 반영)
코드나 정적 파일(HTML, CSS, JS)을 수정하면 **실시간으로 반영(Hot Reload)**됩니다.
```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### ✅ 일반 실행 모드
추가적인 감지 기능 없이 안정적으로 서버를 실행합니다.
```bash
uv run main.py
```

---

## 🔗 접속 안내
서버가 실행되면 터미널에 출력되는 주소로 접속하세요. 보통 다음과 같습니다:
- **로컬 접속**: `http://localhost:8000`
- **외부/네트워크 접속**: `http://<서버-IP>:8000`

---

## 🛠️ 기술 스택
- **Backend**: FastAPI
- **Frontend**: Vanilla JS, Modern CSS (Glassmorphism)
- **Deployment**: Uvicorn
- **Package Manager**: uv