@echo off
chcp 65001
cd /d "%~dp0"

echo [INFO] 점심 추천 봇 서버(Kakao) 실행 준비 중...

REM 1. 서비스 모드에서 타임아웃 방지를 위해 업데이트를 선택적으로 수행 (기본 생략)
if "%1"=="--update" (
    echo [INFO] 최신 코드를 받아옵니다...
    git pull
    echo [INFO] 라이브러리 설치 확인 중...
    pip install -r requirements.txt >nul
)

REM 2. Python 경로 찾기
set PYTHON_CMD=python
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
    ) else (
        if exist "C:\Python312\python.exe" (
            set PYTHON_CMD="C:\Python312\python.exe"
        ) else if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
            set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
            set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        ) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
            set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        )
    )
)

REM 3. 가상환경 확인 및 활성화
if not exist venv (
    echo [INFO] 가상환경[venv] 생성 중...
    %PYTHON_CMD% -m venv venv
)
call venv\Scripts\activate

echo.
echo [INFO] 봇 서버를 실행합니다! (포트: 8000)
echo [NOTE] 서비스 모드에서는 별도의 창(Ngrok)이 뜨지 않습니다.
echo [NOTE] Ngrok은 별도의 서비스로 등록하거나 수동 실행을 권장합니다.

REM 서비스 모드(세션 0)에서는 창을 띄울 수 없으므로 start 대신 주석 처리하거나 필요 시 백그라운드 실행 고려
REM start "Ngrok Tunnel" run_ngrok.bat

echo.
echo [%DATE% %TIME%] Starting bot_server.py...
%PYTHON_CMD% bot_server.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 서버가 종료되었습니다 [Error Code: %errorlevel%].
    REM 서비스 모드에서는 pause를 사용하면 안 됩니다.
)
