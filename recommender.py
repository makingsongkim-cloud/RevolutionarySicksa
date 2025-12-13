import random
import urllib.parse
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None

import lunch_data
from lunch_data import TAG_SOUP, TAG_HOT, TAG_NOODLE, TAG_SPICY, TAG_HEAVY, TAG_LIGHT, TAG_MEAT, TAG_RICE
from history_manager import LunchHistory

class LunchRecommender:
    def __init__(self):
        self.history_mgr = LunchHistory()
        self.menus = lunch_data.MENUS

    def _get_coords(self, location):
        """간단한 좌표 매핑 (키 입력이 없으면 서울 기준)."""
        # 최소 맵핑만 사용 (무료 API라 폭넓은 지오코딩을 하지 않음)
        coords_map = {
            "seoul": (37.5665, 126.9780),
            "서울": (37.5665, 126.9780),
            "sangam-dong": (37.5795, 126.8890),
            "상암동": (37.5795, 126.8890),
            "mapo-gu": (37.5665, 126.9018),
            "마포구": (37.5665, 126.9018),
            "gangnam": (37.4979, 127.0276),
            "강남": (37.4979, 127.0276),
        }
        key = (location or "").lower().strip()
        # 단순히 쉼표 앞부분만 사용 (예: "Seoul,KR")
        if "," in key:
            key = key.split(",")[0].strip()
        return coords_map.get(key, coords_map["seoul"])

    def _weather_from_code(self, code):
        """Open-Meteo weathercode -> 간단한 한글 상태."""
        if code in [0]:
            return "맑음"
        if code in [1, 2, 3, 45, 48]:
            return "흐림"
        if code in [51, 53, 55, 56, 57, 61, 63, 65, 80, 81, 82, 95, 96, 99]:
            return "비"
        if code in [71, 73, 75, 77, 85, 86]:
            return "눈"
        return "흐림"

    def _fetch_wttr(self, target_location):
        encoded_loc = urllib.parse.quote_plus(target_location)
        res = requests.get(f"https://wttr.in/{encoded_loc}?format=%C+%t", timeout=3)
        if res.status_code != 200:
            return None, None

        text = res.text.strip()
        parts = text.split()
        if len(parts) >= 2:
            cond_text = " ".join(parts[:-1]).lower()
            temp_text = parts[-1]
        else:
            cond_text = text.lower()
            temp_text = ""

        condition = "맑음"
        if "rain" in cond_text or "drizzle" in cond_text or "shower" in cond_text:
            condition = "비"
        elif "snow" in cond_text:
            condition = "눈"
        elif "cloud" in cond_text or "overcast" in cond_text or "mist" in cond_text or "fog" in cond_text:
            condition = "흐림"
        elif "sun" in cond_text or "clear" in cond_text:
            condition = "맑음"

        try:
            t_val_str = temp_text.replace("+", "").replace("°C", "").replace("C", "")
            t_val = int(t_val_str)
            if t_val >= 28 and condition not in ["비", "눈"]:
                condition = "더움"
        except:
            pass

        return condition, temp_text

    def _fetch_open_meteo(self, target_location):
        lat, lon = self._get_coords(target_location)
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        res = requests.get(url, timeout=4)
        if res.status_code != 200:
            return None, None

        data = res.json()
        current = data.get("current_weather") or {}
        temp = current.get("temperature")
        code = current.get("weathercode")
        if temp is None or code is None:
            return None, None
        condition = self._weather_from_code(code)
        return condition, f"{round(temp)}°C"

    def detect_city_by_ip(self):
        """간단한 IP 기반 위치 추정 (도시명 반환)"""
        if not REQUESTS_AVAILABLE:
            return None
            
        try:
            res = requests.get("https://ipapi.co/json", timeout=3)
            if res.status_code == 200:
                data = res.json()
                city = data.get("city")
                country = data.get("country_code")
                if city and country:
                    return f"{city},{country}"
                if city:
                    return city
        except Exception:
            pass
        return None

    def get_weather(self, location=None):
        """날씨 가져오기: wttr.in 우선, 실패 시 Open-Meteo fallback (상태 + 온도)"""
        if not REQUESTS_AVAILABLE:
            return None, None
            
        try:
            config = lunch_data.load_config()
            target_location = location or config.get("location", "Seoul")
            # 1) wttr.in 우선
            cond, temp = self._fetch_wttr(target_location)
            # 2) 실패 시 Open-Meteo fallback
            if cond is None:
                cond, temp = self._fetch_open_meteo(target_location)
            return cond, temp
        except Exception:
            return None, None # 에러 시 None

    def refresh_data(self):
        """데이터 갱신 (가게 추가/삭제 후 호출)"""
        # main에서 lunch_data.refresh_menus()가 호출된 상태라고 가정하거나, 직접 호출
        # 여기서는 이미 갱신된 lunch_data.MENUS를 다시 바인딩
        self.menus = lunch_data.MENUS

    def recommend(self, weather=None, cuisine_filters=None, mood=None):
        """
        추천 로직:
        1. 최근 먹은 메뉴(2일 내) 제외
        2. 쿠진(Cuisine) 필터링
        3. 날씨 가중치 부여
        4. 기분(Mood) 가중치 부여
        """
        # 데이터가 갱신되었을 수 있으므로 다시 로드 (혹은 self.menus 사용)
        # self.menus가 초기화 안되어있으면 로드
        if not hasattr(self, 'menus'):
            self.refresh_data()
            
        # 1. 필터링 (최근 먹은 것 제외)
        recent_eaten = self.history_mgr.get_recent_menus(days=2)
        candidates = [m for m in self.menus if m['name'] not in recent_eaten]

        # 2. 쿠진 필터링
        if cuisine_filters:
            candidates = [m for m in candidates if m.get('cuisine') in cuisine_filters]

        if not candidates:
            if cuisine_filters:
                 candidates = [m for m in self.menus if m.get('cuisine') in cuisine_filters]
            else:
                 candidates = self.menus

        if not candidates:
            return None

        # 3. 가중치 계산
        weighted_candidates = []
        
        for menu in candidates:
            score = 10
            tags = menu.get('tags', [])

            # 날씨 반영
            if weather in ["비", "눈", "흐림"]:
                # 국물 요리: 최우선 (+20점)
                if TAG_SOUP in tags:
                    score += 20
                # 따뜻한 면 요리: 우선 (+15점)
                elif TAG_NOODLE in tags and TAG_HOT in tags:
                    score += 15
                # 그냥 따뜻한 요리: 보통 (+5점)
                elif TAG_HOT in tags:
                    score += 5
                # 국물 없는 메뉴: 감점 (-10점)
                else:
                    score -= 10
            elif weather == "더움":
                # 뜨거운 메뉴: 큰 감점 (-15점)
                if TAG_HOT in tags:
                    score -= 15
                # 가벼운 메뉴: 가산점 (+10점)
                if TAG_LIGHT in tags:
                    score += 10

            # 기분 반영 (보통, 화남, 행복, 우울, 피곤)
            if mood == "화남": # 매운거, 묵직한거
                if TAG_SPICY in tags: score += 5
                if TAG_HEAVY in tags: score += 3
            elif mood == "행복": # 고기, 맛있는거
                if TAG_MEAT in tags: score += 5
            elif mood == "우울": # 달달한게 없으니... 탄수화물/고기?
                if TAG_HEAVY in tags or TAG_MEAT in tags: score += 3
                if TAG_SPICY in tags: score += 3 # (매운걸로 풀기)
            elif mood == "피곤": # 고기, 밥 (든든)
                # 고기+밥 조합: 최고 (+15점)
                if TAG_RICE in tags and TAG_MEAT in tags:
                    score += 15
                # 국물+고기 조합: 우수 (+12점)
                elif TAG_SOUP in tags and TAG_MEAT in tags:
                    score += 12
                # 그냥 고기나 밥: 보통 (+4점)
                elif TAG_RICE in tags or TAG_MEAT in tags:
                    score += 4
                
            weighted_candidates.append((menu, score))

        # 4. 선택
        total_score = sum(score for _, score in weighted_candidates)
        pick = random.choices(
            [m for m, _ in weighted_candidates], 
            weights=[s for _, s in weighted_candidates], 
            k=1
        )[0]
        
        return pick
