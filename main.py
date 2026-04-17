import socket
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

def get_local_ip():
    """로컬 네트워크 IP 주소를 가져옵니다."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 연결을 시도하지 않고 IP를 확인하기 위해 외부 범용 IP 사용
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

# static 디렉토리의 정적 파일 서빙
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8000
    
    print("\n" + "="*50)
    print(f"🚀 Kanban Web App이 실행되었습니다!")
    print(f"🔗 접속 주소: http://{local_ip}:{port}")
    print("="*50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
