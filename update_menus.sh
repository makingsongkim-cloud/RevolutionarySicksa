#!/bin/bash
# 메뉴 업데이트 자동화 스크립트

echo "🔄 메뉴 데이터 동기화 중..."

# 1. 홈 디렉토리에서 복사
cp ~/.lunch_siksa/menus.json ./menus.json

# 2. Git에 추가
git add menus.json

# 3. 커밋
git commit -m "메뉴 업데이트 $(date '+%Y-%m-%d %H:%M')"

# 4. GitHub에 푸시
git push

echo "✅ 완료! Streamlit Cloud가 곧 업데이트됩니다."
