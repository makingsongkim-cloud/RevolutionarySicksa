# 프로젝트 이동 및 업데이트 가이드

이 문서는 현재 작업 중인 `점심 추천` 프로젝트를 다른 컴퓨터로 옮기고, 이후 변경 사항을 동기화하는 방법을 설명합니다.

## 방법 1: Git 사용 (권장)

가장 안전하고 편리한 방법입니다. 소스 코드를 GitHub 같은 원격 저장소에 올리고, 다른 컴퓨터에서 받아서 사용합니다.

### 1. 초기 이전 (처음 옮길 때)

**기존 컴퓨터에서:**
1. GitHub에 새 Repository를 만듭니다.
2. 프로젝트 폴더에서 터미널을 열고 다음 명령어를 입력합니다:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin [GitHub 리포지토리 주소]
   git push -u origin main
   ```

**새 컴퓨터에서:**
1. 프로젝트를 저장할 폴더에서 터미널을 엽니다.
2. 코드를 받아옵니다:
   ```bash
   git clone [GitHub 리포지토리 주소]
   cd [프로젝트 폴더명]
   ```
3. 필요한 라이브러리를 설치합니다:
   ```bash
   pip install -r requirements.txt
   ```
4. `.env` 파일을 생성하고 필요한 API 키 등을 입력합니다. (보안상 Git에 올라가지 않았을 수 있습니다)

### 2. 수정 사항 발생 시 업데이트

**수정한 컴퓨터에서:**
```bash
git add .
git commit -m "수정 내용 설명"
git push
```

**업데이트를 받을 컴퓨터에서:**
```bash
git pull
```

---

## 방법 2: 폴더째로 복사 (비권장)

USB나 클라우드 드라이브(Google Drive, Dropbox 등)를 이용해 폴더를 통째로 옮기는 방법입니다. **주의: 실수로 최신 파일을 덮어쓰거나, 파일이 꼬일 위험이 큽니다.**

### 1. 초기 이전

1. `점심 추천` 폴더를 통째로 복사해서 새 컴퓨터로 옮깁니다. (단, `.venv` 같은 가상환경 폴더는 제외하는 것이 좋습니다. 새 컴퓨터에서 다시 만드는 게 낫습니다.)
2. 새 컴퓨터에서 터미널을 열고 프로젝트 폴더로 이동합니다.
3. 필요한 라이브러리를 설치합니다:
   ```bash
   pip install -r requirements.txt
   ```

### 2. 수정 사항 발생 시 업데이트

**수정이 생기면:**
1. 수정한 파일만 정확히 찾아서 새 컴퓨터의 해당 위치에 덮어쓰기 합니다.
2. **또는**, 프로젝트 폴더 전체를 다시 복사해서 새 컴퓨터에 덮어씁니다.
   - ⚠️ **주의**: 새 컴퓨터에서 따로 설정한 내용이나, 로그 파일 등이 사라질 수 있습니다.
   - 덮어쓰기 전에 기존 폴더를 백업(`점심 추천_backup` 등)해두는 것을 추천합니다.

---

## 팁: 실행 환경 설정 (Windows PC 기준)

Windows PC로 옮기셨다면, 제가 만들어둔 **배치 파일(.bat)**을 사용하면 아주 편합니다.

### 1. Python 설치
새 컴퓨터에 Python이 없다면 먼저 설치해야 합니다.
- [Python 공식 홈페이지](https://www.python.org/downloads/)에서 다운로드 (설치 시 **"Add Python to PATH"** 체크박스 필수!)

### 2. 간편 실행 (더블 클릭)
폴더 안에 만들어둔 파일을 더블 클릭만 하세요. 자동으로 필요한 거 설치하고 실행됩니다.

*   **`run_app.bat`**: PC 프로그램(창) 버전 실행
*   **`run_web.bat`**: 웹페이지 버전 실행

### 3. 수동 실행 (직접 입력 시)
만약 직접 검은화면(CMD)에서 하고 싶다면:

```cmd
REM 1. 폴더 이동
cd "폴더경로"

REM 2. 가상환경 생성 (처음 한 번만)
python -m venv venv

REM 3. 가상환경 켜기
venv\Scripts\activate

REM 4. 라이브러리 설치
pip install -r requirements.txt

REM 5. 실행
python main.py
REM 또는
streamlit run app.py
```

---

## 팁: Git 설치하기 (다음 업데이트를 편하게 하려면)

이번엔 파일 옮기느라 고생하셨지만, 새 컴퓨터에 **Git**을 깔아두면 다음부턴 명령어 한 줄로 끝납니다.

### 1. Git 설치
1. [Git 공식 홈페이지](https://git-scm.com/download/win)에서 `Click here to download` 버튼을 눌러 설치합니다.
2. 설치할 때 옵션이 많은데, 그냥 계속 **Next**만 눌러서 넘겨도 됩니다.
3. 설치가 끝나면, **PowerShell**이나 **CMD** 창을 껐다가 다시 켜세요.

### 2. 이제 업데이트가 쉬워집니다!
다음에 또 수정할 일이 생기면?
1. **Mac에서:** `git push`로 올리고,
2. **PC에서:** 폴더에서 우클릭 -> `Git Bash Here` 또는 터미널 열고:
   ```bash
   git pull
   ```
이러면 수정된 파일만 자동으로 싹 받아옵니다!
