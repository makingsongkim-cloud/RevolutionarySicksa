@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DDMC Bot Server Runner

echo ========================================
echo [INFO] 점심 추천 봇 서버 실행 준비
echo ========================================

REM 0. .env 파일 자동 생성 (없으면)
if not exist .env (
    echo [SETUP] .env 파일이 없습니다. 자동 생성 중...
    (
        echo GEMINI_API_KEY=AIzaSyBmHyX4eCMjOGfIxwlXYtGE67OyvcbOMfY,AIzaSyCHaEZkJIw9_hVXga8IGqpxnm401DnzvwU,AIzaSyAlflrQ883GL-cWbCJP9J2EA0RGWIEGMNU,AIzaSyCX6sMpC0DOm-7IbQRNg6LoQVtsthBzCPI,AIzaSyDDS2my5kVgsRZBkUVYqA60x7vTGUGMpkk,AIzaSyALRI2OjqDHCxVdqNypUvSfxjTR5kMQaUs
        echo GEMINI_MODEL=gemini-2.5-flash-lite
    ) > .env
    echo [SETUP] .env 파일 생성 완료!
    echo.
)

pause

REM 1. Python 감지
set PYTHON_CMD=python
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
    ) else (
        echo [ERROR] Python을 찾을 수 없습니다! (python 또는 py 명령어가 필요합니다)
        echo 설치해주세요: https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

REM 2. 가상환경 확인 및 활성화 (있으면)
if exist venv (
    echo [INFO] 가상환경 활성화...
    call venv\Scripts\activate
)

REM 3. 메인 실행 루프
:loop
echo.
echo [1] 포트 8000 정리 중...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do (
    echo   - 포트 8000 사용 중인 프로세스(PID: %%a) 종료...
    taskkill /f /pid %%a >nul 2>&1
)

echo [2] bot_server.py 실행...
%PYTHON_CMD% bot_server.py

echo.
echo ⚠️ 서버가 종료되었습니다! (에러 코드를 확인하세요)
echo 5초 뒤에 재시작합니다... (종료하려면 창을 닫으세요)
timeout /t 5
goto loop
