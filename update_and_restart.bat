@echo off
chcp 65001 >nul
echo ========================================
echo 봇 서버 업데이트 및 재시작
echo ========================================
echo.

echo [1/3] Git Pull (최신 코드 받기)...
git pull

echo.
echo [2/3] Ngrok 터널 실행...
start "Ngrok Tunnel" call run_ngrok.bat
timeout /t 1 /nobreak >nul

echo.
echo [3/3] 봇 서버 실행 (새 창)...
start "DDMC Bot Server" cmd /c "call run_bot.bat"

echo.
echo ========================================
echo 완료! 봇 서버 창이 새로 열렸습니다.
echo 이 창은 3초 뒤에 닫힙니다.
echo ========================================
timeout /t 3
exit
