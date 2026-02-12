@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================
echo 봇 서버 업데이트 및 재시작 (Improved)
echo ========================================
echo.

echo [1/4] Git Pull (최신 코드 받기)...
git pull origin main
if %ERRORLEVEL% neq 0 (
    echo.
    echo ⚠️ [WARN] Git Pull 중 경고가 발생했으나 계속 진행합니다.
    echo (이미 최신이거나 사소한 경고일 수 있습니다.)
)

echo.
echo [2/4] 환경 설정 및 파일 동기화...
if not exist "%USERPROFILE%\.lunch_siksa\" mkdir "%USERPROFILE%\.lunch_siksa\"
if exist menus.json (
    copy /Y menus.json "%USERPROFILE%\.lunch_siksa\menus.json" >nul
    echo   - menus.json 동기화 완료
)

if not exist .env (
    echo   - .env 생성 중...
    (
        echo GEMINI_API_KEY=AIzaSyBmHyX4eCMjOGfIxwlXYtGE67OyvcbOMfY,AIzaSyCHaEZkJIw9_hVXga8IGqpxnm401DnzvwU,AIzaSyAlflrQ883GL-cWbCJP9J2EA0RGWIEGMNU,AIzaSyCX6sMpC0DOm-7IbQRNg6LoQVtsthBzCPI,AIzaSyDDS2my5kVgsRZBkUVYqA60x7vTGUGMpkk,AIzaSyALRI2OjqDHCxVdqNypUvSfxjTR5kMQaUs
        echo GEMINI_MODEL=gemini-2.5-flash-lite
    ) > .env
)

echo.
echo [3/4] 기존 프로세스 종료...
taskkill /F /IM ngrok.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DDMC Bot Server" >nul 2>&1
timeout /t 1 /nobreak >nul

echo.
echo [4/4] 서버 시작...
echo   - Ngrok 실행 중...
start "Ngrok Tunnel" cmd /c "run_ngrok.bat"
timeout /t 2 /nobreak >nul

echo   - 봇 서버 실행 중...
start "DDMC Bot Server" cmd /c "run_bot.bat"

echo.
echo ========================================
echo ✅ 모든 작업이 완료되었습니다!
echo 새 창에서 봇 서버가 실행됩니다.
echo 이 창은 잠시 후 자동으로 닫힙니다.
echo ========================================
timeout /t 5
exit
