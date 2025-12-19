@echo off
echo ========================================
echo 봇 서버 업데이트 및 재시작
echo ========================================
echo.

echo [1/3] 봇 서버 프로세스 종료 중...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq bot_server*" 2>nul
if %errorlevel% equ 0 (
    echo 봇 서버가 종료되었습니다.
) else (
    echo 실행 중인 봇 서버가 없습니다.
)
timeout /t 2 /nobreak >nul
echo.

echo [2/3] Git Pull 실행 중...
git pull
if %errorlevel% neq 0 (
    echo Git Pull 실패! 에러를 확인하세요.
    pause
    exit /b 1
)
echo Git Pull 완료!
echo.

echo [3/3] 봇 서버 시작 중...
start "Ngrok Tunnel" call run_ngrok.bat
timeout /t 1 /nobreak >nul
start "DDMC Bot Server" python bot_server.py
timeout /t 2 /nobreak >nul
echo.

echo ========================================
echo 완료! 봇 서버가 시작되었습니다.
echo ========================================
echo.
pause
