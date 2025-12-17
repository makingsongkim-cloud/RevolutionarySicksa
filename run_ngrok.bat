@echo off
echo [INFO] Ngrok 실행 도우미
echo [INFO] 8000번 포트를 외부에 엽니다.
echo.
echo 명령어가 실행되지 않으면 Ngrok을 설치해야 합니다. (https://ngrok.com/download)
echo.

ngrok http 8000

pause
