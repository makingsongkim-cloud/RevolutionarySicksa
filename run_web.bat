@echo off
chcp 65001
cd /d "%~dp0"

echo [INFO] 점심 추천 웹페이지 실행 준비 중...

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python이 설치되어 있지 않습니다.
    pause
    exit /b
)

if not exist venv (
    echo [INFO] 가상환경(venv) 생성 중...
    python -m venv venv
)

call venv\Scripts\activate

echo [INFO] 라이브러리 설치 확인 중...
pip install -r requirements.txt >nul

echo.
echo [INFO] 브라우저를 실행합니다...
echo.

streamlit run app.py

pause
