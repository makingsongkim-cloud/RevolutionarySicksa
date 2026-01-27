@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo 봇 서버 업데이트 및 재시작
echo ========================================
echo.

echo [1/4] Git Pull (최신 코드 받기)...
git pull

echo.
echo [2/4] .env 파일 확인...
if not exist .env (
    echo   [SETUP] .env 파일이 없습니다. 자동 생성 중...
    (
        echo GEMINI_API_KEY=AIzaSyBmHyX4eCMjOGfIxwlXYtGE67OyvcbOMfY,AIzaSyCHaEZkJIw9_hVXga8IGqpxnm401DnzvwU,AIzaSyAlflrQ883GL-cWbCJP9J2EA0RGWIEGMNU,AIzaSyCX6sMpC0DOm-7IbQRNg6LoQVtsthBzCPI,AIzaSyDDS2my5kVgsRZBkUVYqA60x7vTGUGMpkk,AIzaSyALRI2OjqDHCxVdqNypUvSfxjTR5kMQaUs
        echo GEMINI_MODEL=gemini-2.5-flash-lite
    ) > .env
    echo   [SETUP] .env 파일 생성 완료!
) else (
    echo   [OK] .env 파일 존재
)

echo.
echo [3/4] Ngrok 터널 실행...
start "Ngrok Tunnel" call run_ngrok.bat
timeout /t 1 /nobreak >nul

echo.
echo [4/4] 봇 서버 실행 (새 창)...
start "DDMC Bot Server" cmd /k "call run_bot.bat"

echo.
echo ========================================
echo 완료! 봇 서버 창이 새로 열렸습니다.
echo 이 창은 3초 뒤에 닫힙니다.
echo ========================================
timeout /t 3
exit
