@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ========================================
echo 봇 서버 업데이트 및 재시작 (Improved)
echo ========================================
echo.

echo [1/4] Git Pull (최신 코드 받기)...
REM Git pull 시도 및 에러 체크
git pull > git_pull_result.txt 2>&1
type git_pull_result.txt

findstr /C:"error:" git_pull_result.txt >nul
if %errorlevel% equ 0 (
    echo.
    echo ❌ [ERROR] Git Pull 중 오류가 발생했습니다.
    echo 로컬에서 코드를 직접 수정하셨다면 'git reset --hard'가 필요할 수 있습니다.
    echo 업데이트를 건너뛰고 재시작하시겠습니까? (Y/N)
    set /p "CHOICE="
    if /i "!CHOICE!" neq "Y" (
        del git_pull_result.txt
        pause
        exit /b 1
    )
)
del git_pull_result.txt

echo.
echo [1.5/4] 메뉴 파일 동기화 (%USERPROFILE%\.lunch_siksa\menus.json)...
if not exist "%USERPROFILE%\.lunch_siksa\" mkdir "%USERPROFILE%\.lunch_siksa\"
if exist menus.json (
    copy /Y menus.json "%USERPROFILE%\.lunch_siksa\menus.json"
    echo   [OK] 메뉴 파일 업데이트 완료!
) else (
    echo   [WARN] menus.json을 찾을 수 없습니다.
)

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
echo [3/4] 기존 프로세스 강제 종료...
REM Ngrok 및 Bot 프로세스 종료
taskkill /F /IM ngrok.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM python3.exe >nul 2>&1

REM "DDMC Bot Server" 타이틀을 가진 배치 파일 창 종료 (루프 탈출용)
taskkill /F /FI "WINDOWTITLE eq DDMC Bot Server" >nul 2>&1
timeout /t 1 /nobreak >nul

echo.
echo [4/4] Ngrok 터널 실행...
start "Ngrok Tunnel" call run_ngrok.bat
timeout /t 2 /nobreak >nul

echo.
echo [5/5] 봇 서버 실행 (새 창)...
start "DDMC Bot Server" cmd /c "call run_bot.bat"

echo.
echo ========================================
echo 완료! 봇 서버 창이 새로 열렸습니다.
echo 이 창은 3초 뒤에 닫힙니다.
echo ========================================
timeout /t 3
exit
