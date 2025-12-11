
# 메뉴 데이터베이스
# (이름, 구역, 태그 리스트, 기본 카테고리명, 음식 종류)
import json
import os
import shutil
import sys

# 구역 상수
AREA_BASEMENT = "회사 지하식당"
AREA_YTN = "YTN 지하식당"
AREA_MEOKJA = "건너편 먹자골목"

# 태그 상수
TAG_HEAVY = "heavy"      # 무거운/든든한
TAG_LIGHT = "light"      # 가벼운/부담없는
TAG_SOUP = "soup"        # 국물
TAG_SPICY = "spicy"      # 매운/자극적
TAG_NOODLE = "noodle"    # 면
TAG_RICE = "rice"        # 밥
TAG_MEAT = "meat"        # 고기
TAG_HOT = "hot"          # 뜨거운 요리

# 음식 종류 (Cuisine)
CUISINE_KOREAN = "한식"
CUISINE_CHINESE = "중식"
CUISINE_JAPANESE = "일식"
CUISINE_WESTERN = "양식"
CUISINE_SNACK = "분식"
CUISINE_OTHER = "기타"

JSON_FILE = "menus.json"
CONFIG_FILE = "config.json"

# Persistent Storage Logic for App Bundle
# When frozen (PyInstaller), we cannot write to the bundle dir.
# use ~/.lunch_siksa instead.
DATA_DIR = os.path.join(os.path.expanduser("~"), ".lunch_siksa")
if not os.path.exists(DATA_DIR):
    try:
        os.makedirs(DATA_DIR)
    except:
        pass # Fallback to current dir if permission denied (rare)

# Paths inside user data dir
JSON_FILE = os.path.join(DATA_DIR, "menus.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# Path to bundled assets (works for both source and PyInstaller)
BASE_DIR = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
BUNDLED_JSON = os.path.join(BASE_DIR, "menus.json")


# 기본 시드 데이터
DEFAULT_MENUS = [
    {"name": "구내식당", "area": AREA_BASEMENT, "category": "백반", "cuisine": CUISINE_KOREAN, "tags": [TAG_RICE, TAG_LIGHT]},
    {"name": "마라탕", "area": AREA_MEOKJA, "category": "마라탕", "cuisine": CUISINE_CHINESE, "tags": [TAG_SOUP, TAG_SPICY, TAG_HOT]},
    {"name": "돈까스", "area": AREA_YTN, "category": "돈까스", "cuisine": CUISINE_WESTERN, "tags": [TAG_MEAT, TAG_HEAVY]},
    {"name": "김치찌개", "area": AREA_MEOKJA, "category": "찌개", "cuisine": CUISINE_KOREAN, "tags": [TAG_SOUP, TAG_HOT, TAG_SPICY]},
    {"name": "샌드위치", "area": AREA_YTN, "category": "샌드위치", "cuisine": CUISINE_WESTERN, "tags": [TAG_LIGHT]}
]

def load_menus():
    """JSON 파일에서 메뉴 리스트 로드 (없으면 번들 메뉴를 복사하거나 기본값 반환)"""
    if not os.path.exists(JSON_FILE):
        # 우선 번들된 menus.json이 있으면 사용자 데이터 디렉토리로 복사
        if os.path.exists(BUNDLED_JSON):
            try:
                shutil.copy(BUNDLED_JSON, JSON_FILE)
            except Exception as e:
                print(f"Error copying bundled menus: {e}")
        else:
            # 번들 파일도 없으면 기본값으로 기록
            try:
                with open(JSON_FILE, 'w', encoding='utf-8') as f:
                    json.dump(DEFAULT_MENUS, f, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"Error writing default menus: {e}")
                return list(DEFAULT_MENUS)

    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if not data:
                return list(DEFAULT_MENUS)
            return data
    except Exception as e:
        print(f"Error loading menus: {e}")
        return list(DEFAULT_MENUS)

def save_new_menu(name, area, category, cuisine, tags):
    """새 메뉴 저장"""
    menus = load_menus()
    
    # 중복 체크 (이름 기준)
    for m in menus:
        if m['name'] == name:
            return False # 이미 존재
            
    new_menu = {
        "name": name,
        "area": area,
        "category": category,
        "cuisine": cuisine,
        "tags": tags
    }
    menus.append(new_menu)
    
    try:
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(menus, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Error saving menu: {e}")
        return False

def delete_menu(name):
    """메뉴 삭제"""
    menus = load_menus() # 파일에서 최신 로드
    
    # 해당 이름 제외하고 필터링
    new_menus = [m for m in menus if m['name'] != name]
    
    if len(menus) == len(new_menus):
         return False # 삭제할 게 없음
         
    try:
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_menus, f, ensure_ascii=False, indent=4)
        refresh_menus() # 전역 변수 갱신
        return True
    except Exception as e:
        print(f"Error deleting menu: {e}")
        return False

def update_menu(original_name, new_data):
    """메뉴 정보 수정"""
    menus = load_menus()
    
    # 1. 이름이 변경되었다면 중복 체크
    if original_name != new_data['name']:
        for m in menus:
            if m['name'] == new_data['name']:
                return False, "이미 존재하는 이름입니다."
    
    # 2. 찾아서 업데이트
    found = False
    for i, m in enumerate(menus):
        if m['name'] == original_name:
            menus[i] = new_data
            found = True
            break
            
    if not found:
        return False, "수정할 메뉴를 찾을 수 없습니다."
        
    try:
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(menus, f, ensure_ascii=False, indent=4)
        refresh_menus()
        return True, "수정되었습니다."
    except Exception as e:
        print(f"Error updating menu: {e}")
        return False, f"저장 중 오류 발생: {e}"

DEFAULT_CONFIG = {"location": "Seoul"}

def load_config():
    """설정 로드"""
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return DEFAULT_CONFIG

def save_config(new_config):
    """설정 저장"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(new_config, f, indent=4)
        return True
    except Exception as e:
        print(f"Config save error: {e}")
        return False

# 초기 로드 (전역 변수로 사용될 때)
MENUS = load_menus()

def refresh_menus():
    """메뉴 다시 로드 (추가 후 호출용)"""
    global MENUS
    MENUS = load_menus()
