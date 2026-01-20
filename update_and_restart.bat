@echo off
chcp 65001 >nul
echo ========================================
echo 봇 서버 업데이트 및 재시작
echo ========================================
echo.

echo [1/3] Git Pull (최신 코드 받기)...
git pull
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Git Pull 실패! 인터넷 연결이나 충돌을 확인하세요.
    echo 일단 무시하고 기존 코드로 실행하시겠습니까? (Y/N)
    set /p "ALLOW_CONTINUE=> "
    if /i not "%ALLOW_CONTINUE%"=="y" exit /b 1
)

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
