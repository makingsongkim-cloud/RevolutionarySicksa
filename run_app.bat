@echo off
chcp 65001
cd /d "%~dp0"

echo [INFO] 점심 추천 앱 실행 준비 중...

REM python 명령어 확인
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python이 설치되어 있지 않거나 경로 설정이 안되어 있습니다.
    echo [INFO] Microsoft Store나 python.org에서 Python을 설치해주세요.
    pause
    exit /b
)

REM 가상환경 확인 및 생성
if not exist venv (
    echo [INFO] 가상환경(venv)이 없어서 새로 만듭니다...
    python -m venv venv
)

REM 가상환경 활성화
call venv\Scripts\activate

REM 필수 라이브러리 설치
echo [INFO] 필요한 라이브러리를 확인하고 설치합니다...
pip install -r requirements.txt >nul

echo.
echo [INFO] 앱을 실행합니다!
echo.

python main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 실행 중 오류가 발생했습니다.
    pause
)
