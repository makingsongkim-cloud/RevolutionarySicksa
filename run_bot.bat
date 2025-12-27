@echo off
chcp 65001
cd /d "%~dp0"

echo [INFO] 점심 추천 봇 서버(Kakao) 실행 준비 중...
echo [INFO] 최신 코드를 받아옵니다...
git pull
echo.


REM Try to find Python
set PYTHON_CMD=python

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] 'python' 명령어를 찾지 못했습니다.
    echo [INFO] 'py' [Python Launcher]를 찾아봅니다...
    
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
        echo [SUCCESS] 'py' 명령어로 실행합니다!
    ) else (
        echo [INFO] 기본 경로에서 Python을 찾아봅니다...
        
        if exist "C:\Python312\python.exe" (
            set PYTHON_CMD="C:\Python312\python.exe"
        ) else if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
            set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
            set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        ) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
            set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        ) else (
            echo [CRITICAL ERROR] Python을 도저히 찾을 수 없습니다.
            echo 1. Python이 설치되었는지 확인해주세요.
            echo 2. 설치 시 'Add to PATH'를 체크했는지 확인해주세요.
            echo 3. 컴퓨터를 재부팅하고 다시 시도해보세요.
            pause
            exit /b
        )
    )
)

if not exist venv (
    echo [INFO] 가상환경[venv] 생성 중...
    %PYTHON_CMD% -m venv venv
)

call venv\Scripts\activate

echo [INFO] 라이브러리 설치 확인 중...
pip install -r requirements.txt >nul

echo.
echo [INFO] 봇 서버를 실행합니다! (포트: 8000)
echo [INFO] Ngrok 터널링 프로그램도 새 창에서 같이 실행합니다.

start "Ngrok Tunnel" run_ngrok.bat
echo.

:server_loop
echo [%DATE% %TIME%] Starting bot_server.py...
%PYTHON_CMD% bot_server.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 서버가 예기치 않게 종료되었습니다 [Error Code: %errorlevel%].
)

echo [%DATE% %TIME%] 5초 후에 자동으로 재시작합니다...
echo 중단하려면 이 창을 닫거나 Ctrl+C를 누르세요.
timeout /t 5 >nul
goto server_loop
