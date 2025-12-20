
import requests
import sys

def check():
    print("서버 상태를 확인합니다...")
    hosts = ["http://127.0.0.1:8000", "http://localhost:8000"]
    success = False

    for host in hosts:
        try:
            # 단순 접속 확인
            response = requests.get(f"{host}/docs", timeout=2)
            if response.status_code == 200:
                print(f"✅ {host} : 정상 작동 중!")
                success = True
                break
        except requests.exceptions.ConnectionError:
            continue
        except Exception as e:
            print(f"❓ {host} 오류: {e}")

    if not success:
        print("\n❌ 연결 실패!")
        print("서버가 꺼져있거나 8000번 포트가 아닙니다.")
        print("'run_bot.bat'이나 'python bot_server.py'를 먼저 실행해주세요.")

if __name__ == "__main__":
    check()
    input("\n엔터를 누르면 종료합니다...")
