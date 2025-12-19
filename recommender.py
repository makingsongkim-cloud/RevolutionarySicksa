import random
import urllib.parse
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None

import lunch_data
from lunch_data import TAG_SOUP, TAG_HOT, TAG_NOODLE, TAG_SPICY, TAG_HEAVY, TAG_LIGHT, TAG_MEAT, TAG_RICE, TAG_PREMIUM
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

    def recommend(self, weather=None, cuisine_filters=None, mood=None, excluded_menus=None):
        """
        추천 로직:
        1. 최근 먹은 메뉴(2일 내) 제외
        2. 제외 리스트(excluded_menus) 제외 (재추천 시 사용)
        3. 쿠진(Cuisine) 필터링
        4. 날씨 가중치 부여
        5. 기분(Mood) 가중치 부여
        """
        # 데이터 갱신 확인
        if not hasattr(self, 'menus'):
            self.refresh_data()
            
        # 1. 필터링 (최근 먹은 것 제외)
        recent_eaten = self.history_mgr.get_recent_menus(days=2)
        
        # 제외 목록 통합
        final_excluded = set(recent_eaten)
        if excluded_menus:
            final_excluded.update(excluded_menus)
            
        candidates = [m for m in self.menus if m['name'] not in final_excluded]

        # 2. 쿠진 필터링
        if cuisine_filters:
            candidates = [m for m in candidates if m.get('cuisine') in cuisine_filters]

        # 후보가 없으면 필터 완화 (제외 목록은 유지하되, 쿠진 필터만 해제 고민... 일단은 쿠진 필터 우선 해제)
        if not candidates:
            if cuisine_filters:
                 # 쿠진 필터만 해제하고 다시 시도
                 candidates = [m for m in self.menus if m['name'] not in final_excluded]
            
            # 그래도 없으면... 어쩔 수 없이 전체에서 다시 뽑음 (최근 먹은거라도)
            if not candidates:
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
            
            elif weather == "더위" or weather == "더움":
                # 뜨거운 메뉴: 큰 감점 (-15점)
                if TAG_HOT in tags:
                    score -= 15
                # 시원한/가벼운 메뉴: 가산점 (+15점)
                if TAG_LIGHT in tags or TAG_NOODLE in tags: # 냉면 등 가정
                    score += 15
            
            elif weather == "추위":
                # 따뜻한 국물: 최우선 (+20점)
                if TAG_SOUP in tags and TAG_HOT in tags:
                    score += 20
                # 그냥 따뜻한거: 우선 (+15점)
                elif TAG_HOT in tags:
                    score += 15
                # 차가운거: 감점 (-20점)
                elif TAG_LIGHT in tags: 
                    score -= 20
            
            elif weather == "한파": # 영하 날씨 (NEW)
                # 1. 위치 점수 (실내 우대)
                if menu.get('area') in ["회사 지하식당", "회사 1층"]:
                    score += 100  # 밖으로 나가지 말라고 강력 추천 (40->100)
                else:
                    score -= 50  # 밖에 나가는 건 감점 (-20->-50)
                
                # 2. 메뉴 점수
                if TAG_SOUP in tags and TAG_HOT in tags:
                    score += 20
                elif TAG_HOT in tags:
                    score += 15
                elif TAG_LIGHT in tags:
                    score -= 30 # 추운데 차가운건 절대 금지

            elif weather == "맑음":
                # 딱히 가리는 거 없음, 가벼운 거 살짝 우대?
                if TAG_LIGHT in tags:
                    score += 5

            # 기분 반영 (보통, 화남, 행복, 우울, 피곤)
            if mood == "화남": # 매운거, 국물, 고기/밥 강추
                if TAG_SPICY in tags: score += 20
                if TAG_SOUP in tags or TAG_HOT in tags: score += 12
                if TAG_MEAT in tags: score += 8
                if TAG_RICE in tags: score += 5
                if TAG_LIGHT in tags: score -= 8
            elif mood == "행복": # 고기, 풍미 있는 메뉴
                if TAG_MEAT in tags: score += 8
                if TAG_PREMIUM in tags: score += 5
            elif mood == "우울": # 든든/탄수/국물/매운거
                if TAG_RICE in tags and TAG_MEAT in tags: score += 15
                if TAG_SOUP in tags: score += 10
                if TAG_HEAVY in tags: score += 8
                if TAG_SPICY in tags: score += 5
                if TAG_LIGHT in tags: score -= 5
            elif mood == "피곤": # 에너지 보충
                if TAG_RICE in tags and TAG_MEAT in tags:
                    score += 20
                elif TAG_SOUP in tags and TAG_MEAT in tags:
                    score += 15
                elif TAG_RICE in tags or TAG_MEAT in tags:
                    score += 8
                if TAG_LIGHT in tags: score -= 5
            elif mood == "플렉스": # 비싼거, 법카 (Premium)
                if TAG_PREMIUM in tags:
                    score += 200  # 무조건 우선 (60->200)
                elif TAG_MEAT in tags and TAG_HEAVY in tags:
                    score += 15  # 고기+든든함 차선책
                else:
                    score -= 30  # 플렉스 찾는데 가벼운 메뉴는 제외
            elif mood == "다이어트": # 가볍게
                if TAG_LIGHT in tags:
                    score += 60
                elif TAG_HEAVY in tags or TAG_PREMIUM in tags:
                    score -= 60 # 다이어트인데 무거운/플렉스 금지
                elif TAG_MEAT in tags:
                    score -= 10
            
            # [NEW] 회사 1층(비싼 곳) 패널티 로직
            # "플렉스" 모드가 아니고, "한파"도 아닐 때 -> 회사 1층 추천 제외 (점수 대폭 깎음)
            # (단, 한파여도 플렉스가 아니면 1층이 비쌀 수 있으니... 사용자가 "비싸니 돈 많을 때만 추천해"라고 함)
            # => 한파 때는 "실내"라는 장점이 크므로 패널티를 좀 줄이거나 상쇄해야 함. 
            # 하지만 사용자가 "보통 여길 추천받으면 신뢰도가 떨어져"라고 했으므로, 플렉스 아닐 땐 기본적으로 막는게 맞음.
            # 예외: 정말 나가기 싫은 "한파"일 때는 지하 vs 1층 중 지하가 우선되도록 유도.
            if menu.get('area') == "회사 1층" and mood != "플렉스":
                # 한파라서 실내 점수(+40)를 받았더라도, 비싸다는 인식이 강하므로 패널티 부여
                # 한파(+40) - 패널티(??)
                # 사용자는 "돈이 많을 때만 추천해야 한다"고 했음.
                score -= 50 

            weighted_candidates.append((menu, score))

        # 4. 선택
        total_score = sum(score for _, score in weighted_candidates)
        if total_score <= 0: # 점수가 다 깎여서 0 이하가 되면 균등 확률
             pick = random.choice([m for m, _ in weighted_candidates])
        else:
            pick = random.choices(
                [m for m, _ in weighted_candidates], 
                weights=[s for _, s in weighted_candidates], 
                k=1
            )[0]
        
        return pick
