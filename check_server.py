
import requests
import sys

def check():
    print("="*40)
    print(" [DDMC 봇 서버 연결 테스트] ")
    print("="*40)
    
    hosts = ["http://127.0.0.1:8000", "http://localhost:8000"]
    endpoints = ["/", "/docs"]
    success = False

    for host in hosts:
        for ep in endpoints:
            url = f"{host}{ep}"
            print(f"📡 시도 중: {url}...", end=" ", flush=True)
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    print("✅ 성공!")
                    success = True
                    break
                else:
                    print(f"⚠️ 상태 코드 {response.status_code}")
            except requests.exceptions.ConnectionError:
                print("❌ 거부됨 (OFF)")
            except Exception as e:
                print(f"❌ 오류: {e}")
        if success: break

    if success:
        print("\n🎉 서버가 정상적으로 응답하고 있습니다!")
    else:
        print("\n" + "!"*40)
        print(" [연결 실패] 서버가 꺼져 있는 것 같습니다.")
        print("!"*40)
        print("1. 'DDMC Bot Server' 창이 켜져 있는지 확인하세요.")
        print("2. 'Ngrok' 창이 켜져 있는지 확인하세요.")
        print("3. 같은 PC에서 실행 중인지 확인하세요.")

if __name__ == "__main__":
    check()
    input("\n엔터를 누르면 종료합니다...")
