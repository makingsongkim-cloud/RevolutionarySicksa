@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DDMC Bot Server Runner

echo ========================================
echo [INFO] 점심 추천 봇 서버 실행 준비
echo ========================================

REM 1. Python 감지
set PYTHON_CMD=python
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
    )
)

REM 2. 가상환경 확인 및 활성화 (있으면)
if exist venv (
    echo [INFO] 가상환경(venv) 활성화...
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
