from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
import recommender
import os
import random
import asyncio
import time
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from session_manager import session_manager
from rate_limiter import rate_limiter
from datetime import datetime, timedelta

# 날씨 캐시 (10분마다 갱신)
weather_cache = {
    "condition": None,
    "temp": None,
    "mapped_weather": None,
    "last_updated": None
}

# 환경 변수 로드
load_dotenv()

# 기본 로깅 설정 (파일 + 콘솔)
LOG_PATH = os.path.join(os.path.dirname(__file__), "bot.log")
logger = logging.getLogger("lunch_bot")
logger.setLevel(logging.INFO)
logger.handlers.clear()

file_handler = RotatingFileHandler(
    LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
console_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok", "message": "DDMC Lunch Bot Server is running!"}

# Gemini API 설정 (멀티 키 로테이션 지원)
GEMINI_FORCE_LOCAL = os.getenv("GEMINI_FORCE_LOCAL", "").lower() in ("1", "true", "yes", "y")
API_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEY", "").split(",") if k.strip()]
current_key_index = 0

gemini_model = None
intent_model = None
GEMINI_AVAILABLE = False

def reconfigure_gemini():
    global gemini_model, intent_model, GEMINI_AVAILABLE, current_key_index
    
    if not API_KEYS:
        GEMINI_AVAILABLE = False
        return False

    try:
        import google.generativeai as genai
        from google.generativeai.types import HarmCategory, HarmBlockThreshold
        
        target_key = API_KEYS[current_key_index]
        genai.configure(api_key=target_key)

        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }

        INTENT_CONFIG = {"temperature": 0.1, "max_output_tokens": 100, "top_p": 0.8, "top_k": 40}
        RESPONSE_CONFIG = {"temperature": 0.85, "max_output_tokens": 200, "top_p": 0.8, "top_k": 40}
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

        gemini_model = genai.GenerativeModel(model_name, safety_settings=safety_settings, generation_config=RESPONSE_CONFIG)
        intent_model = genai.GenerativeModel(model_name, safety_settings=safety_settings, generation_config=INTENT_CONFIG)
        
        GEMINI_AVAILABLE = True
        logger.info(f"✅ Gemini API 키 전환 성공! (Key Index: {current_key_index}, Model: {model_name})")
        return True
    except Exception as e:
        logger.error(f"❌ Gemini API 재설정 실패 (Index {current_key_index}): {e}")
        return False

if not GEMINI_FORCE_LOCAL and API_KEYS:
    reconfigure_gemini()
else:
    if GEMINI_FORCE_LOCAL:
        logger.warning("⚠️ Gemini API 강제 비활성화 모드입니다.")
    else:
        logger.warning("⚠️ 등록된 GEMINI_API_KEY가 없습니다.")

# 키워드 매핑 딕셔너리 (Fallback용)
CUISINE_KEYWORDS = {
    "한식": ["한식", "한국", "김치", "된장", "비빔밥", "국밥", "찌개"],
    "중식": ["중식", "중국", "짜장", "짬뽕", "탕수육", "마라"],
    "일식": ["일식", "일본", "초밥", "라멘", "돈까스", "우동"],
    "양식": ["양식", "서양", "파스타", "스테이크", "피자", "햄버거"],
    "분식": ["분식", "떡볶이", "김밥", "라면", "순대"]
}

WEATHER_KEYWORDS = {
    "비": ["비", "우산", "장마", "비오", "빗"],
    "눈": ["눈", "함박눈", "눈오", "눈이"],
    "더위": ["더워", "덥", "여름", "무더위", "더운"],
    "추위": ["추워", "춥", "겨울", "쌀쌀"],
    "한파": ["한파", "개춥", "너무춥", "얼어", "영하"]
}

MOOD_KEYWORDS = {
    "화남": [
        "화나", "화난", "화났", "화나다", "화난다", "짜증", "열받", "스트레스", "매운", "빡쳐", "빡치", "빡치네", "빡친다",
        "좆", "좆같", "씨발", "시발", "개같", "개새", "엿", "엿먹",
        "존나", "개짜증", "열불", "승질", "미치겠",
        "거지같", "그지같", "거지 같다", "그지 같다", "더럽"
    ],
    "행복": ["행복", "기분좋", "신나", "즐거", "월급"],
    "우울": ["우울", "슬퍼", "꿀꿀", "다운"],
    "피곤": ["피곤", "지쳐", "힘들", "녹초", "탈진", "기운없", "지침"],
    "졸림": ["졸려", "졸림", "잠와", "잠옴", "꾸벅", "하품"],
    "배고픔": ["배고파", "배고픔", "허기", "굶주", "배꼽시계", "시장"],
    "외로움": ["외로", "쓸쓸", "심심", "혼자", "고독"],
    "플렉스": ["비싼", "고급", "법카", "플렉스", "월급", "보너스", "돈지랄"],
    "다이어트": ["다이어트", "살빼", "가벼운", "샐러드", "관리", "식단"]
}

# [공용 객체] 서버 시작 시 한 번만 생성하여 I/O 부하 감소
r = recommender.LunchRecommender()

# Input Models for Kakao Skill Payload
class Action(BaseModel):
    params: Dict[str, Any] = {}

class User(BaseModel):
    id: str

class UserRequest(BaseModel):
    utterance: str
    user: Optional[User] = None

class SkillPayload(BaseModel):
    userRequest: UserRequest
    action: Action = Action()


def get_josa(word: str, particle_type: str) -> str:
    """
    한글 단어의 받침 유무에 따라 적절한 조사를 붙여 반환합니다.
    particle_type: "은/는", "이/가", "을/를", "와/과"
    """
    if not word:
        return ""
        
    last_char = word[-1]
    # 한글 유니코드 범위: 0xAC00 ~ 0xD7A3
    if not (0xAC00 <= ord(last_char) <= 0xD7A3):
        # 한글이 아니면 기본값(앞쪽 조사) 반환 (예: Pizza는)
        return f"{word}{particle_type.split('/')[0]}"
    
    # 받침 유무 확인 ((유니코드 - 0xAC00) % 28 > 0 이면 받침 있음)
    has_batchim = (ord(last_char) - 0xAC00) % 28 > 0
    
    particles = particle_type.split('/')
    if has_batchim:
        return f"{word}{particles[0]}" # 은, 이, 을, 과
    else:
        return f"{word}{particles[1]}" # 는, 가, 를, 와


import asyncio
INTENT_TIMEOUT_SEC = 1.8
GENERATION_TIMEOUT_SEC = 2.5

# [최적화] 지수 백오프 기반 쿨다운 시스템
GEMINI_INITIAL_COOLDOWN = 30.0 # 초기 쿨다운 30초
GEMINI_MAX_COOLDOWN = 600.0    # 최대 쿨다운 10분
GEMINI_BACKOFF_FACTOR = 2.0    # 배수
GEMINI_COOLDOWN_UNTIL = 0.0
current_gemini_cooldown_sec = GEMINI_INITIAL_COOLDOWN


def _is_rate_limited_error(err: Exception) -> bool:
    msg = str(err).lower()
    return "429" in msg or "quota" in msg or "rate limit" in msg


def _gemini_in_cooldown() -> bool:
    return time.time() < GEMINI_COOLDOWN_UNTIL


def _set_gemini_cooldown() -> None:
    global GEMINI_COOLDOWN_UNTIL, current_gemini_cooldown_sec, current_key_index
    
    # [멀티 키] 429 에러 발생 시 즉시 다음 키로 전환 시도
    if len(API_KEYS) > 1:
        old_idx = current_key_index
        current_key_index = (current_key_index + 1) % len(API_KEYS)
        logger.warning(f"🔄 Rate Limit 감지! 키 전환 시도: Index {old_idx} -> {current_key_index}")
        if reconfigure_gemini():
            # 키 전환 성공 시 쿨다운 없이 즉시 재시도 가능하도록 설정 (단, 백오프는 유지하여 안전성 확보)
            GEMINI_COOLDOWN_UNTIL = 0
            return

    GEMINI_COOLDOWN_UNTIL = time.time() + current_gemini_cooldown_sec
    logger.warning(f"⚠️ 모든 키 한도 초과 또는 단일 키 쿨다운 진입: {current_gemini_cooldown_sec:.1f}초")
    current_gemini_cooldown_sec = min(GEMINI_MAX_COOLDOWN, current_gemini_cooldown_sec * GEMINI_BACKOFF_FACTOR)

def _reset_gemini_backoff() -> None:
    """성공 시 백오프 초기화"""
    global current_gemini_cooldown_sec
    if current_gemini_cooldown_sec > GEMINI_INITIAL_COOLDOWN:
        current_gemini_cooldown_sec = GEMINI_INITIAL_COOLDOWN
        logger.info("✅ Gemini 백오프가 초기화되었습니다.")

async def run_gemini_with_timeout(model, prompt: str, timeout_sec: float, log_label: str):
    """Execute Gemini call with a strict timeout and return text or None."""
    if _gemini_in_cooldown():
        remaining = GEMINI_COOLDOWN_UNTIL - time.time()
        logger.warning(f"{log_label} skipped: Gemini in cooldown ({remaining:.1f}s left)")
        return None
    try:
        # 가급적 자체 비동기 메서드 사용
        response = await asyncio.wait_for(model.generate_content_async(prompt), timeout=timeout_sec)
        result = (response.text or "").strip()
        if result:
            _reset_gemini_backoff() # 성공하면 백오프 초기화
        return result
    except asyncio.TimeoutError:
        logger.warning(f"{log_label} timeout after {timeout_sec}s")
    except Exception as e:
        if _is_rate_limited_error(e):
            _set_gemini_cooldown()
            logger.warning(f"{log_label} rate-limited; entering cooldown")
        logger.warning(f"{log_label} fail: {e}")
    return None

def format_history(conversation_history: List[Dict], limit: int = 2) -> str:
    """대화 히스토리 포맷팅 (토큰 절약)"""
    if not conversation_history:
        return ""
    return "\n".join([
        f"{h['role']}: {h['message']}"
        for h in conversation_history[-limit:]
    ])
def get_meal_label(now: Optional[datetime] = None) -> str:
    """현재 시간 기준 추천 식사 라벨 반환."""
    current = now or datetime.now()
    hour = current.hour
    # 10시~10:59: 아침
    if 10 <= hour < 11:
        return "아침"
    # 11시~18시: 점심
    if 11 <= hour < 18:
        return "점심"
    # 18시~20시: 저녁
    if 18 <= hour < 20:
        return "저녁"
    # 기타 시간: 아침(10시 이전) / 저녁(20시 이후)
    return "아침" if hour < 10 else "저녁"


def get_requested_meal_label(utterance: str) -> Optional[str]:
    """사용자 발화에서 명시된 식사 라벨을 추출합니다."""
    if not utterance:
        return None
    candidates = {
        "아침": ["아침"],
        "점심": ["점심"],
        "저녁": ["저녁"],
    }
    utter = utterance.replace(" ", "")
    earliest = None
    for label, keywords in candidates.items():
        for kw in keywords:
            idx = utter.find(kw)
            if idx != -1 and (earliest is None or idx < earliest[0]):
                earliest = (idx, label)
    return earliest[1] if earliest else None


def get_time_context(utterance: str) -> Dict[str, Optional[str]]:
    """현재/요청 식사 라벨 및 늦은 저녁 여부를 반환합니다."""
    now = datetime.now()
    current_label = get_meal_label(now)
    requested_label = get_requested_meal_label(utterance)
    is_late_evening = current_label == "저녁" and now.hour >= 20
    return {
        "current_label": current_label,
        "requested_label": requested_label,
        "is_late_evening": is_late_evening,
    }


def contains_explain_keyword(utterance: str) -> bool:
    """이유/왜 질문 여부를 간단히 판단합니다."""
    if not utterance:
        return False
    text = utterance.lower()
    return any(k in text for k in ["왜", "이유", "why", "어째서", "이유는"])

async def analyze_intent_with_gemini(utterance: str, conversation_history: List[Dict]) -> Dict[str, Any]:
    """Gemini API를 사용하여 사용자 의도를 분석합니다. (Short Prompt + Strict Config)"""
    if _gemini_in_cooldown():
        return analyze_intent_fallback(utterance)
    try:
        history_text = format_history(conversation_history, limit=2)
        
        from datetime import datetime
        now_str = datetime.now().strftime("%I:%M%p") # 시간 포맷 단축

        prompt = f"""의도 분석 (JSON):
히스토리:
{history_text}
입력: "{utterance}" ({now_str})

분류:
1. intent: recommend (메뉴추천요청), explain (이유), reject (거절), accept (수락), casual (잡담/일반질문), help (도움)
2. casual_type: greeting, thanks, chitchat (casual일때)
3. emotion: negative, neutral, positive
4. filter: [한식, 중식, 일식, 양식, 분식]
5. weather: 비, 눈, 더위, 추위, 한파
6. mood: 피곤, 행복, 우울, 화남, 다이어트, 플렉스

JSON만 출력:"""

        # 타임아웃 짧게(응답성 우선)
        response = await asyncio.wait_for(intent_model.generate_content_async(prompt), timeout=INTENT_TIMEOUT_SEC)
        result_text = response.text.strip()
        
        # JSON 파싱 cleanup
        if "```" in result_text:
            result_text = result_text.replace("```json", "").replace("```", "").strip()
            
        import json
        result = json.loads(result_text)
        
        # 키 이름 호환성 (filter -> cuisine_filters)
        if 'filter' in result:
            result['cuisine_filters'] = result.pop('filter')
            
        return result
        
    except (asyncio.TimeoutError, Exception) as e:
        if _is_rate_limited_error(e):
            _set_gemini_cooldown()
            logger.warning("⚠️ Intent 분석 rate-limited; entering cooldown")
        logger.warning(f"⚠️ Intent 분석 실패/타임아웃: {e}")
        return analyze_intent_fallback(utterance)


def analyze_intent_fallback(utterance: str) -> Dict[str, Any]:
    """
    키워드 매칭으로 사용자 의도를 분석합니다 (Fallback).
    """
    utterance_lower = utterance.lower()
    
    # 의도 분석
    intent = "casual"  # 기본값 변경: recommend -> casual (아무 말이나 하면 잡담으로 처리)
    casual_type = "chitchat"
    
    # 일상 대화 패턴 (명확한 인사/감사 등)
    if any(word in utterance_lower for word in ["안녕", "안녕하세요", "하이", "ㅎㅇ", "hello", "hi", "헬로", "헬로우", "반가", "반가워", "여보세요", "누구", "넌누구", "이름이", "봇이름"]):
        intent = "casual"
        casual_type = "greeting"
    elif any(word in utterance_lower for word in ["고마", "감사", "thanks", "thank", "ㅇㅋ", "알았어", "ㄱㅅ", "ㄳ"]):
        intent = "casual"
        casual_type = "thanks"
    elif any(word in utterance_lower for word in ["왜", "이유", "why", "어째서", "이유는", "설명해", "왜죠"]):
        # [CRITICAL] 설명 요청은 최우선순위로 처리하고 즉시 반환 (오버라이드 방지)
        return {"intent": "explain", "casual_type": None, "emotion": "neutral", "cuisine_filters": [], "weather": None, "mood": None, "tag_filters": []}
    elif any(word in utterance_lower for word in ["싫", "별로", "다른", "아니", "no", "패스", "바꿔", "말고", "담에", "나중에"]):
        intent = "reject"
    # recommend (명확한 키워드가 있을 때만 추천)
    elif any(word in utterance_lower for word in ["추천", "메뉴", "밥", "식사", "배고파", "뭐먹지", "골라줘", "아무거나", "랜덤", "알아서", "해봐", "해", "고", "배곱", "출출", "허기"]):
        intent = "recommend"
    # accept (짧은 긍정)
    elif any(word in utterance_lower for word in ["응", "ㅇㅇ", "ㅇㅋ", "좋아", "콜", "고고"]):
        intent = "accept"
    # help (도움말)
    elif any(word in utterance_lower for word in ["도움", "사용법", "설명", "help", "어떻게", "기능"]):
        intent = "help"
    # 긍정 피드백 패턴
    elif any(word in utterance_lower for word in ["좋", "맛있", "거기", "그거", "먹을", "ok", "yes", "굿"]):
        intent = "accept"
    
    # 질문형 어미 체크 (보강)
    if any(utterance_lower.endswith(ending) for ending in ["?", "냐", "까", "니", "요", "죠", "가", "나"]):
        # 추천 키워드가 없으면 잡담 유지
        if intent == "recommend" and not any(word in utterance_lower for word in ["추천", "메뉴", "점심", "밥"]):
             intent = "casual"
             casual_type = "chitchat"
    
    # 감정 분석
    emotion = "neutral"
    if any(word in utterance_lower for word in ["좆같", "짜증", "열받", "화나", "힘들", "우울"]):
        emotion = "negative"
    elif any(word in utterance_lower for word in ["행복", "좋", "신나", "즐거"]):
        emotion = "positive"
    
    # 음식 종류 추출
    cuisine_filters = []
    for cuisine, keywords in CUISINE_KEYWORDS.items():
        if any(keyword in utterance_lower for keyword in keywords):
            cuisine_filters.append(cuisine)
            
    # [NEW] 음식 태그 추출 (국물, 면, 고기 등) -> search_filters로 활용
    # CUISINE_KEYWORDS에 없는 '특징' 기반 키워드
    tag_keywords_map = {
        "soup": ["국물", "찌개", "탕", "전골", "국밥"],
        "noodle": ["면", "국수", "우동", "라면", "짬뽕", "짜장", "파스타", "소바"],
        "meat": ["고기", "육류", "돈까스", "스테이크", "갈비", "불고기", "제육"],
        "rice": ["밥", "덮밥", "볶음밥", "비빔밥", "리조또"],
        "spicy": ["매운", "빨간", "얼큰", "칼칼"],
        "light": ["가벼운", "샐러드", "샌드위치", "다이어트"],
        "heavy": ["든든", "푸짐", "해장"]
    }
    
    tag_filters = []
    for tag, keywords in tag_keywords_map.items():
        if any(keyword in utterance_lower for keyword in keywords):
            tag_filters.append(tag)
            
    # 날씨 추출
    weather = None
    for weather_type, keywords in WEATHER_KEYWORDS.items():
        if any(keyword in utterance_lower for keyword in keywords):
            weather = weather_type
            break
    
    # 기분 추출
    mood = None
    for mood_type, keywords in MOOD_KEYWORDS.items():
        if any(keyword in utterance_lower for keyword in keywords):
            mood = mood_type
            break
    # [NEW] 음식 키워드, 기분, 날씨 중 하나라도 발견되면 추천 Intent로 유도
    if (cuisine_filters or tag_filters or mood or weather) and intent == "casual":
        intent = "recommend"

    return {
        "intent": intent,
        "casual_type": casual_type,
        "emotion": emotion,
        "cuisine_filters": cuisine_filters,
        "weather": weather,
        "mood": mood,
        "tag_filters": tag_filters # [NEW] 태그 필터 추가
    }


def generate_explanation_fallback(rec: Dict, weather: Optional[str] = None, mood: Optional[str] = None) -> str:
    """
    메뉴 추천 이유를 로컬에서 생성 (Fallback)
    - 단순 템플릿 조합이지만, 태그/날씨/기분을 반영하여 그럴싸하게 만듦
    """
    name = rec.get('name', '이 메뉴')
    category = rec.get('category', '음식')
    tags = rec.get('tags', [])
    
    # 1. 태그 기반 논리
    reason_logic = f"**{category}** 메뉴로 유명한 곳이에요."
    
    if "spicy" in tags:
        reason_logic = "스트레스 확 풀리는 매콤한 맛이 일품이거든요! 🔥"
    elif "soup" in tags:
        if weather and weather in ["비", "눈", "흐림", "추위", "장마"]:
            reason_logic = "오늘처럼 쌀쌀한 날씨엔 이런 뜨끈한 국물이 최고잖아요. 🍲"
        else:
            reason_logic = "속이 확 풀리는 국물 맛이 끝내주거든요."
    elif "meat" in tags:
        if mood == "우울" or mood == "화남":
            reason_logic = "기분이 저기압일 땐 역시 고기 앞으로 가야죠! 🍖"
        else:
            reason_logic = "든든하게 배 채우기엔 고기가 딱이니까요."
    elif "light" in tags:
        if mood == "다이어트":
             reason_logic = "가볍게 관리하기 딱 좋은 메뉴라 골랐어요. 🥗"
        else:
             reason_logic = "더부룩하지 않고 깔끔하게 즐길 수 있는 메뉴예요. 🥗"
    elif "noodle" in tags:
        reason_logic = "후루룩 면치기 하기 딱 좋은 날이니까요! 🍜"

    # 2. 날씨/기분 추가 멘트
    extra = ""
    if weather:
        weather_notes = {
            "비": "비가 와서 따뜻하고 든든한 메뉴가 잘 어울려요. ☔",
            "눈": "추운 날씨엔 따뜻한 메뉴가 딱이에요. ❄️",
            "흐림": "쌀쌀할 수 있으니 속 편한 메뉴를 골랐어요. ☁️",
            "더위": "더운 날씨엔 너무 무거운 메뉴는 피하는 게 좋아요. ☀️",
            "추위": "추울 땐 뜨끈한 메뉴가 최고죠. 🥶",
            "한파": "한파엔 따뜻하게 든든하게 먹는 게 좋아요. 🧊",
            "맑음": "맑은 날엔 가볍게 즐기기 좋은 메뉴를 골랐어요. 🌤️",
        }
        extra = f"\n\n(참고: {weather_notes.get(weather, '날씨에 맞춰 무난한 메뉴로 골랐어요.')})"
    
    # 3. 마무리 (다양성)
    import random
    closers = [
        "분명 만족스러운 식사가 되실 거예요! 😊",
        "한 번 드셔보시면 제 마음을 아실 거예요!",
        "마스터님 입맛에도 딱 맞을 거라고 확신해요. ✨",
        "후회 없으실 선택이 될 거예요. 👍",
        "제가 강력 추천하는 이유랍니다! 👏"
    ]
    
    return f"'{name}'(을)를 추천한 이유요?\n\n{reason_logic}{extra}\n\n{random.choice(closers)}"


async def generate_casual_response_with_gemini(
    utterance: str,
    casual_type: str,
    conversation_history: List[Dict],
    user_id: str = "Master",
    meal_label: str = "점심",
) -> str:
    """일상 대화 응답 (Short Prompt)"""
    history_text = format_history(conversation_history)
    
    prompt = f"""친근한 챗봇 응답:
히스토리:
{history_text}
사용자: {utterance}
현재 추천 식사: {meal_label}

가이드:
1. 친구처럼 밝고 공감하는 말투 (이모지 사용)
2. 사용자의 말에 맞춰 자연스럽게 대답 (억지로 점심 얘기 꺼내지 말 것)
3. 인사인 경우에는 인사하고 메뉴 추천 받을지 질문
4. 만약 사용자가 배고파하거나 점심 맥락일 때만 메뉴 추천 유도
5. 1-2문장으로 짧게

응답:"""
    
    response_text = await run_gemini_with_timeout(
        gemini_model, prompt, GENERATION_TIMEOUT_SEC, "Casual response"
    )
    if response_text:
        return response_text
    return generate_casual_response_fallback(casual_type, user_id, meal_label=meal_label)


def generate_casual_response_fallback(casual_type: str, user_id: str = "Master", meal_label: str = "점심") -> str:
    """
    일상 대화 기본 응답 (Fallback)
    """
    if casual_type == "greeting":
        return f"안녕하세요! 😊 {meal_label} 추천 받아보실래요?"
    elif casual_type == "thanks":
        return f"천만에요! 맛있게 드세요~ 🍽️ 다음에도 {meal_label} 고민되시면 언제든 불러주세요!"
    else:
        # 야, 등 짧은 호출이나 잡담에 대한 대응
        messages = [
            f"네! {meal_label} 메뉴 고민이신가요? 🤔",
            f"부르셨나요? 맛있는 {meal_label} 추천해드릴까요? 😋",
            f"심심하신가요? 저랑 {meal_label} 메뉴 고르기 해요! 🎲",
            f"네! 무슨 일이신가요? 배고프시면 '{meal_label} 추천'이라고 말해보세요!",
            f"음... 글쎄요? {meal_label} 메뉴 추천이라면 자신 있습니다! 😎",
            "무슨 말씀인지 잘 모르겠지만... 배고프신 건 아니죠? 밥이나 먹으러 가요! 🍚",
            "혹시 비밀번호 물어보신 거 아니죠? 🤐 (농담입니다)",
            f"오늘 {meal_label} 뭐 드실까요? 제가 골라드릴게요! 🍽️",
            "배고프신가요? 맛집 추천해드릴게요! 😊",
            f"{meal_label} 시간이네요! 어떤 메뉴 드시고 싶으세요? 🤗",
            f"저를 부르셨나요? {meal_label} 메뉴 고민 해결사 등장! 💪",
            f"네네! 오늘도 맛있는 {meal_label} 찾아드릴게요! ✨",
            f"무슨 일이신가요? {meal_label} 추천이 필요하시면 말씀해주세요! 🙌"
        ]
        import random
        return random.choice(messages)


def build_emotion_prefix(intent_data: Dict, choice: Optional[Dict] = None) -> str:
    """감정/기분에 따라 멘트 앞머리 고정."""
    mood = intent_data.get("mood")
    emotion = intent_data.get("emotion")
    
    # 메뉴가 '가벼운' 것인지 확인
    is_light = False
    if choice and "light" in choice.get("tags", []):
        is_light = True
    
    if mood == "화남":
        return "맛있는 거 먹고 화 풀어요! 🔥\n"
    if mood == "우울":
        return "기분 전환엔 맛있는 게 최고! 🌈\n"
    if mood == "피곤":
        if is_light:
            return "지친 몸에 부담 없는 에너지! ⚡\n"
        return "에너지 채우는 든든한 한 끼! 💪\n"
    if mood == "행복":
        return "기분 좋은 날엔 맛있는 걸로! 😊\n"
    if mood == "플렉스":
        return "오늘은 제대로 flex! 💳\n"
    if mood == "다이어트":
        return "가볍게 관리하는 날! 🥗\n"
    
    if emotion == "negative":
        if is_light:
            return "지친 마음을 달래줄 깔끔한 한 끼! 🙏\n"
        return "힘든 날엔 든든하게 먹고 기운 내요! 🙏\n"
    if emotion == "positive":
        return "좋은 기분 이어가요! 😄\n"
    return ""


async def generate_explanation_with_gemini(utterance: str, last_recommendation: Dict, conversation_history: List[Dict], weather: Optional[str] = None, mood: Optional[str] = None) -> str:
    """추천 이유 설명 (Short Prompt)"""
    rec = last_recommendation
    info = f"{rec['name']}({rec.get('category')}), {rec.get('area')}, 특징:{','.join(rec.get('tags',[]))}"
    context = f"날씨:{weather}, 기분:{mood}" if weather or mood else ""
    
    prompt = f"""메뉴 추천 이유 설명:
사용자: "{utterance}"
추천: {info}
{context}

가이드:
1. 메뉴 특징과 상황(날씨/기분) 연결하여 2-3문장
2. 날씨 정보가 있으면 반드시 언급
3. 위치 장점 언급
4. 친근한 말투, 이모지

응답:"""
    
    response_text = await run_gemini_with_timeout(
        gemini_model, prompt, GENERATION_TIMEOUT_SEC, "Explanation"
    )
    if response_text:
        return response_text
    return generate_explanation_fallback(last_recommendation, weather, mood)

async def generate_response_with_gemini(
    utterance: str,
    choice: dict,
    intent_data: Dict,
    conversation_history: List[Dict],
    meal_label: str = "점심",
) -> str:
    """추천 멘트 생성 (Short Prompt)"""
    # Cooldown 체크 - Rate limit 중이면 즉시 fallback
    if _gemini_in_cooldown():
        return generate_response_message(choice, intent_data, meal_label=meal_label)
    
    name = choice['name']
    category = choice.get('category', '')
    area = choice.get('area', '')
    tags = choice.get('tags', [])
    
    context = f"상황: {intent_data.get('weather')}, {intent_data.get('mood')}, {intent_data.get('cuisine_filters')}"
    emotion = intent_data.get('emotion', 'neutral')
    tone = "위로하는 톤" if emotion == "negative" else "밝은 톤"
    prefix = build_emotion_prefix(intent_data)
    
    prompt = f"""{meal_label} 추천 멘트 작성 ({tone}):
사용자: "{utterance}"
메뉴: {name} ({category}, {area})
특징: {', '.join(tags)}
{context}
현재 추천 식사: {meal_label}

가이드:
1. 친근하게 2문장
2. 추천 이유 핵심만
3. 마지막에 위치/종류 표기 필수

형식:
[멘트]

📍 위치: {area}
🍽️ 종류: {category}"""

    response_text = await run_gemini_with_timeout(
        gemini_model, prompt, GENERATION_TIMEOUT_SEC, "Recommend response"
    )
    if response_text:
        return prefix + response_text
    return generate_response_message(choice, intent_data)


def generate_response_message(choice: dict, intent_data: Dict, meal_label: str = "점심") -> str:
    """
    기본 응답 메시지를 생성합니다 (Fallback).
    """
    name = choice.get('name', '추천 메뉴')
    category = choice.get('category', '')
    area = choice.get('area', '')
    
    cuisine_filters = intent_data.get('cuisine_filters', [])
    weather = intent_data.get('weather')
    mood = intent_data.get('mood')
    emotion = intent_data.get('emotion', 'neutral')
    
    # 감정/기분 고정 프리픽스
    emotion_prefix = build_emotion_prefix(intent_data, choice)
    
    # 상황별 멘트
    import random
    
    # 상황별 멘트 리스트
    prefixes = []
    
    tags = choice.get('tags', [])
    is_light = "light" in tags
    
    if emotion == "negative" and not emotion_prefix:
        if is_light:
            prefixes = [
                "기분이 안 좋으실 땐 깔끔한 음식으로 힐링해봐요! 🌿 ",
                "저런... 😢 맛있는 거 먹고 털어버려요! ",
                "기분 전환에는 가볍고 맛있는 게 최고죠! 🥗 "
            ]
        else:
            prefixes = [
                "힘든 하루시네요 😔 든든하고 맛있는 걸로 기운 내세요! ",
                "저런... 😢 맛있는 거 먹고 털어 버려요! ",
                "기분이 안 좋으실 땐 맛있는 게 약이죠! 💊 "
            ]
    elif cuisine_filters:
        f_str = ', '.join(cuisine_filters)
        prefixes = [
            f"{f_str} 좋아하시는군요! ",
            f"오늘은 {f_str} 당기시는 날! ",
            f"{f_str} 맛집을 찾아봤어요! "
        ]
    elif weather == "비":
        prefixes = [
            "비 오는 날엔 이게 최고죠! 🌧️ ",
            "비도 오고 그래서... ☔ ",
            "빗소리 들으면서 먹기 좋은 메뉴! "
        ]
    elif weather == "눈":
        prefixes = [
            "눈 오는 날엔 따뜻한 게 최고! ❄️ ",
            "하얀 눈 보면서 먹으면 더 맛있죠! ☃️ ",
            "추위 녹이는 따뜻한 메뉴! "
        ]
    elif weather == "더위":
        prefixes = [
            "더울 땐 시원한 게 최고! ☀️ ",
            "이열치열, 혹은 시원하게! 🧊 ",
            "더위에 지치지 마세요! "
        ]
    elif weather == "추위":
        prefixes = [
            "추울 땐 따뜻한 게 최고! 🥶 ",
            "뜨끈한 국물이 생각나는 날씨죠! ",
            "몸 녹이는 데는 이게 딱이에요! "
        ]
    elif mood == "피곤" and not emotion_prefix:
        if is_light:
            prefixes = [
                "피곤할 땐 부담 없는 메뉴로 속 편하게! 🍵 ",
                "지친 몸에 에너지를 주는 깔끔한 메뉴! ",
                "가볍게 먹고 푹 쉬세요! ⚡ "
            ]
        else:
            prefixes = [
                "피곤할 땐 든든하게! 💪 ",
                "지친 몸엔 맛있는 밥이 보약! ",
                "에너지 충전 하세요! ⚡ "
            ]
    elif mood == "행복" and not emotion_prefix:
        prefixes = [
            "기분 좋은 날엔 맛있는 걸로! 😊 ",
            "오늘 같은 날은 파티죠! 🎉 ",
            "행복한 기분 그대로 맛있는 식사! "
        ]
    elif mood == "우울" and not emotion_prefix:
        if is_light:
            prefixes = [
                "기분 전환엔 깔끔하고 시원한 거 어떠세요? 🌈 ",
                "우울할 땐 가벼운 산책과 맛있는 한 끼! ",
                "기분 좋아지는 예쁜 메뉴로 골랐어요! "
            ]
        else:
            prefixes = [
                "기분 전환이 필요하시군요! 🌈 ",
                "우울할 땐 맛있는 거 앞으로! ",
                "든든한 거 먹고 기분 풀어봐요! "
            ]
    elif mood == "화남" and not emotion_prefix:
        prefixes = [
            "맛있는 거 먹고 풀어요! 😤 ",
            "스트레스엔 역시 먹는 거죠! 🔥 ",
            "맛있는 걸로 힐링하고 기분 풀어보세요! "
        ]
    
    # 비 오는 날 전용 팁
    rain_tip = ""
    if weather == "비":
        rain_tip = "\n\n💡 **Tip**: 비가 오면 실내가 평소보다 붐빌 수 있으니 조금 더 서둘러 가 보세요! 🏃‍♂️"
    
    selected_prefix = random.choice(prefixes) if prefixes else ""
    cleaned_emotion = emotion_prefix.strip() if emotion_prefix else ""
    cleaned_selected = selected_prefix.strip() if selected_prefix else ""
    if cleaned_emotion and cleaned_selected:
        # 동일/유사 문구면 중복 제거
        if cleaned_emotion == cleaned_selected or cleaned_selected in cleaned_emotion:
            selected_prefix = ""
        else:
            emotion_keywords = ["화", "풀", "맛있는", "스트레스", "기분", "우울", "피곤", "행복"]
            if any(kw in cleaned_emotion and kw in cleaned_selected for kw in emotion_keywords):
                selected_prefix = ""

    message = f"{emotion_prefix}{selected_prefix}추천드립니다: [{name}] 🍜\n\n📍 위치: {area}\n🍽️ 종류: {category}{rain_tip}"
    # 연속 중복 라인 제거
    lines = message.splitlines()
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)
    return "\n".join(deduped)


@app.post("/api/lunch")
async def recommend_lunch(payload: SkillPayload):
    """
    KakaoTalk Skill Endpoint for Lunch Recommendation (Reliability Wrapped)
    """
    total_start = time.time()

    # 1. 사용자 ID 및 기초 정보 추출 (타임아웃 영향 최소화)
    user_id = payload.userRequest.user.id if payload.userRequest.user else "anonymous"
    utterance = payload.userRequest.utterance or ""

    # [긴급 타이브레이커] 4.3초 내에 응답을 못 하면 강제 종료하고 안전 응답 반환
    try:
        start_handle = time.time()
        response = await asyncio.wait_for(
            handle_recommendation_logic(user_id, utterance, payload, total_start),
            timeout=4.3,
        )
        duration = time.time() - start_handle
        logger.info(f"⏱️ Request handled in {duration:.2f}s")
        return response
    except asyncio.TimeoutError:
        timeout_duration = time.time() - total_start
        logger.error(f"🚨 Global Timeout triggered after {timeout_duration:.2f}s")
        # 현재까지 수집된 날씨/기분 정보를 바탕으로 '최선의 로컬 응답' 생성
        weather = weather_cache.get("mapped_weather")
        return get_emergency_fallback_response("global_timeout", utterance=utterance, user_id=user_id, weather=weather)
    except Exception as e:
        logger.exception(f"🚨 Unhandled Error: {e}")
        import traceback
        traceback.print_exc()
        return get_emergency_fallback_response(str(e), utterance=utterance, user_id=user_id)


async def handle_recommendation_logic(
    user_id: str, utterance: str, payload: SkillPayload, start_time: float
):
    """메인 추천 로직 핸들러 (입력 분석 -> 필터링 -> 선택 -> 응답 생성)"""
    total_start = start_time
    
    # [ULTRA FAST TRACK] 0. 로컬 의도 분석 최우선 실행
    # 날씨, 세션, 레이트 리밋 등 무거운 작업 전에 먼저 판단합니다.
    fast_intent = analyze_intent_fallback(utterance)
    
    # [Defensive] "왜"/"이유"는 무조건 설명으로 고정 (Help 오인식 방지)
    if "왜" in utterance or "이유" in utterance:
        fast_intent["intent"] = "explain"
        
    is_help_request = fast_intent.get("intent") == "help"
    is_welcome_event = not utterance.strip() or utterance in ["웰컴", "welcome", "시작"]
    is_short_casual = len(utterance.strip()) <= 2
    has_random_keyword = any(k in utterance for k in ["랜덤", "랜덤추천", "랜덤 추천"])
    time_ctx = get_time_context(utterance)
    current_meal_label = time_ctx["current_label"] or "점심"
    requested_meal_label = time_ctx["requested_label"]
    is_late_evening = bool(time_ctx["is_late_evening"])
    meal_label = requested_meal_label or current_meal_label
    mismatch_notice = (
        f"지금은 {current_meal_label} 시간인데, {meal_label}으로 추천해드릴까요? 😊"
        if requested_meal_label and requested_meal_label != current_meal_label
        else ""
    )
    recommended_in_response = False
    
    # 0.1 웰컴/도움말/단답형 즉시 반환 (0.01초 내 응답 목표)
    if is_welcome_event:
        logger.info("⚡ Ultra Fast Track: Welcome Event")
        # generate_casual_response_fallback는 동기 함수이므로 await 제거
        return get_final_kakao_response(
            generate_casual_response_fallback("greeting", user_id, meal_label=meal_label)
        )
    elif is_help_request:
        logger.info("⚡ Ultra Fast Track: Help Request")
        return get_help_response()
    elif is_short_casual and fast_intent.get("intent") != "explain" and not has_random_keyword:
        logger.info(f"⚡ Ultra Fast Track: Short Casual ({utterance})")
        return get_final_kakao_response(
            generate_casual_response_fallback("chitchat", user_id, meal_label=meal_label)
        )

    # 1. 태아웃 방지용 기록 및 이스터에그
    logger.info(f"[Request Processing] '{utterance}' | user={user_id}")
    
    # 이스터에그
    easter_egg_keywords = [
        "김형석",
        "만든사람",
        "만든 사람",
        "누가만듬",
        "개발자",
        "제작자",
        "누가만들",
        "누가했",
        "누구작품",
        "창조주",
        "주인장",
    ]

    if any(keyword in utterance.replace(" ", "") for keyword in easter_egg_keywords):
        import random

        praise_messages = [
            # ... (찬양 문구 생략/유지) ...
            "🌟 **시스템 경보: 위대한 창조주 감지!** 🌟\n\n앗! 당신은... 이 세상 모든 코드를 지배하고,\n점심 메뉴의 진리를 깨우치신 **김형석님**?! 🙇‍♂️",
            "🕶️ **Top Secret Information**\n\nCode Name: **K.H.S (김형석)**\nRole: The Architect of Lunch (점심의 설계자)",
            "🥘 **푸드 마스터 김형석**\n\n이 봇을 누가 만들었냐고요?\n바로 **김형석**님입니다! (박수 짝짝짝 👏)",
        ]
        return get_final_kakao_response(random.choice(praise_messages))

    # 2. Rate Limiting
    is_allowed, deny_reason = rate_limiter.is_allowed(user_id)
    if not is_allowed:
        return {
            "version": "2.0",
            "template": {"outputs": [{"simpleText": {"text": f"⚠️ {deny_reason}"}}]},
        }

    # 3. 세션 및 날씨 정보 (병렬 시작)
    session = session_manager.get_session(user_id)
    conversation_history = session_manager.get_conversation_history(user_id)

    # [병렬화] 날씨 정보를 미리 가져오기 시작 (메인 로직과 겹치지 않게 비동기 처리)
    async def get_weather_task():
        now = datetime.now()
        if weather_cache["last_updated"] and (now - weather_cache["last_updated"]) < timedelta(minutes=10):
             return weather_cache["mapped_weather"]
        try:
            # 글로벌 객체 r을 활용하거나 별도 처리 (여기서는 독립적으로 날씨만 가져옴)
            # r.get_weather는 내부적으로 requests를 사용하므로 thread에서 별도로 수행
            # 여기서 타임아웃을 너무 짧게 잡으면 항상 실패하므로 내부 requests timeout에 맡깁니다.
            cond, temp = await asyncio.to_thread(r.get_weather)
            
            actual_weather = None
            if cond:
                weather_mapping = {
                    "비": "비", "rain": "비", "rainy": "비",
                    "눈": "눈", "snow": "눈", "snowy": "눈",
                    "맑음": "맑음", "clear": "맑음", "sunny": "맑음",
                    "흐림": "흐림", "cloudy": "흐림", "overcast": "흐림",
                    "더움": "더위", "hot": "더위"
                }
                c_lower = cond.lower()
                for k, v in weather_mapping.items():
                    if k in c_lower:
                        actual_weather = v
                        break
            
            if not actual_weather and temp:
                try:
                    t_val = float(temp.replace("°C", "").replace("℃", "").strip())
                    if t_val < 0: actual_weather = "한파"
                    elif t_val < 10: actual_weather = "추위"
                    elif t_val > 28: actual_weather = "더위"
                except: pass
            
            weather_cache.update({
                "condition": cond, "temp": temp, 
                "mapped_weather": actual_weather, "last_updated": now
            })
            return actual_weather
        except:
            return None

    weather_future = asyncio.create_task(get_weather_task())
    
    # 4. 의도 분석 (Hybrid)
    # (이미 위에서 초반 0. 로컬 분석이 수행되었으므로, 필요한 데이터만 정리)
    # ...
    # [병렬화 결과 획득]
    try:
        # 이미 획득했거나 아주 짧은 대기 (0.1초)
        await asyncio.wait_for(asyncio.shield(weather_future), timeout=0.1)
        actual_weather = weather_cache.get("mapped_weather")
    except:
        actual_weather = weather_cache.get("mapped_weather")
    # 추가된 마스터모드 이스터 에그
    if utterance == "마스터모드":
        logger.info("Easter Egg: Master Mode Activated")
        return get_final_kakao_response("마스터 모드가 활성화되었습니다. (디버깅용)")

    # [병렬화 결과 획득]
    try:
        # 이미 획득했거나 타임아웃 0.2초 내에 확보 시도
        res_weather = await asyncio.wait_for(asyncio.shield(weather_future), timeout=0.2)
        actual_weather = weather_cache.get("mapped_weather") # 캐시 업데이트된 값 사용
    except:
        actual_weather = weather_cache.get("mapped_weather") # 실패 시 기존 캐시

    # 4. 의도 분석 (Smart Patch - Fallback First)


    # 4.1 "날씨" 질문 단독 처리 (Gemini 불필요)
    if (
        "날씨" in utterance
        and len(utterance) < 10
        and not any(k in utterance for k in ["추천", "메뉴", "점심", "밥"])
    ):
        cond, temp = r.get_weather() # Use global r

        cond_display = cond if cond else "정보 없음"
        temp_display = temp if temp else "정보 없음"

        response_text = f"🌡️ 현재 날씨 정보\n\n상태: {cond_display}\n기온: {temp_display}\n\n날씨에 맞는 {meal_label} 추천해드릴까요? 😊"

        session_manager.add_conversation(user_id, "user", utterance)
        session_manager.add_conversation(user_id, "bot", response_text)

        return {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": response_text}}],
                "quickReplies": [
                    {"label": "☔ 날씨에 맞게 추천", "action": "message", "messageText": "날씨에 맞게 추천해줘"}
                ],
            },
        }

    # 4.2 로컬 의도 분석 (Fallback) 선행 호출
    # 키워드 기반으로 1차 판단을 먼저 합니다.
    fast_intent = analyze_intent_fallback(utterance)
    has_target_keyword = bool(
        fast_intent.get("cuisine_filters") or 
        fast_intent.get("tag_filters") or
        fast_intent.get("mood") or
        fast_intent.get("weather")
    )
    is_help_request = fast_intent.get("intent") == "help"
    is_welcome_event = not utterance.strip() or utterance in ["웰컴", "welcome", "시작"]

    # 4.3 의도 결정 로직 (Short-circuit)
    if is_welcome_event:
        logger.info("⚡ Fast Track: Welcome Event")
        intent_data = {"intent": "casual", "casual_type": "greeting"}
        GEMINI_AVAILABLE_FOR_REQUEST = False
    elif is_help_request:
        logger.info("⚡ Fast Track: Help Request (Skipping Gemini)")
        intent_data = fast_intent
        GEMINI_AVAILABLE_FOR_REQUEST = False
    elif has_target_keyword:
        logger.info("⚡ Smart Patch: Target Keyword Detected (Skipping Gemini Intent)")
        intent_data = fast_intent
        # 키워드가 있으면 intent를 'recommend'로 강제 (fallback 내부에서 처리되지만 확실히 함)
        intent_data["intent"] = "recommend"
        # 의도 분석은 스킵하지만, 응답 생성 시 Gemini 분위기 조성을 위해 GEMINI_AVAILABLE_FOR_REQUEST는 유지
        GEMINI_AVAILABLE_FOR_REQUEST = GEMINI_AVAILABLE
    elif len(utterance.strip()) <= 2:
        logger.info(f"⚡ Super-Fast Track: Very Short Utterance ({utterance})")
        # 단답형(야, 왜, 어, ㄴ, ㅇ 등)은 Gemini를 거치지 않고 바로 답변
        intent_data = fast_intent
        
        # [FIX] '왜' 같은 질문이 들어왔을 때 intent가 'explain'이면 그대로 유지
        if intent_data.get("intent") == "explain":
            logger.info("  -> Intent is EXPLAIN (Preserving)")
            GEMINI_AVAILABLE_FOR_REQUEST = False # 로컬 설명 생성기로 연결
        else:
            GEMINI_AVAILABLE_FOR_REQUEST = False
    elif len(utterance) < 15 and any(
        k in utterance for k in ["점심", "밥", "뭐먹", "배고파", "랜덤"]
    ):
        logger.info("⚡ Fast Track: Simple Recommend (Skipping Gemini)")
        intent_data = fast_intent
        GEMINI_AVAILABLE_FOR_REQUEST = False
    elif not GEMINI_AVAILABLE:
        logger.info("⚡ Fallback: Gemini Not Configured")
        intent_data = fast_intent
        GEMINI_AVAILABLE_FOR_REQUEST = False
    elif _gemini_in_cooldown():
        logger.info("⚡ Fallback: Gemini Rate Limited (Cooldown)")
        intent_data = fast_intent
        GEMINI_AVAILABLE_FOR_REQUEST = False
    else:
        # 키워드에 걸리지 않는 복잡한 문장이나 일상 대화만 Gemini 사용
        logger.info("🤖 Engine: Gemini Intent Analysis")
        # Gemini 호출 시 타임아웃을 2.5초로 줄여 안전성 확보
        intent_data = await analyze_intent_with_gemini(
            utterance, conversation_history
        )  # Assuming analyze_intent_with_gemini has its own timeout or is wrapped
        GEMINI_AVAILABLE_FOR_REQUEST = True

    intent = intent_data.get("intent", "recommend")
    casual_type = intent_data.get("casual_type")

    # "왜/이유" 질문은 help보다 explain을 우선
    if contains_explain_keyword(utterance):
        intent = "explain"
        intent_data["intent"] = "explain"

    logger.info(
        f"User: {user_id} | Intent: {intent} | Weather: {actual_weather} | Mood: {intent_data.get('mood')} | Utterance: '{utterance}'"
    )

    # 5. 의도별 처리 (기존 로직과 동일하나 요약)
    response_text = ""
    # [특수] 도움말은 즉시 반환
    if intent == "help":
        return get_help_response()

    # 인텐트에 따른 처리 분기
    if intent == "casual":
        if GEMINI_AVAILABLE_FOR_REQUEST and not _gemini_in_cooldown():
            casual_response = await generate_casual_response_with_gemini(
                utterance, casual_type, conversation_history, user_id, meal_label=meal_label
            )
        else:
            casual_response = generate_casual_response_fallback(casual_type, user_id, meal_label=meal_label)

        is_question = any(utterance.strip().endswith(m) for m in ["?", "냐", "까", "니", "요", "죠"])
        has_strong_keyword = any(
            word in utterance.lower() for word in ["점심", "추천", "메뉴", "배고", "식사"]
        )
        has_weak_keyword = "먹" in utterance.lower()

        should_recommend = (
            (has_strong_keyword)
            or (has_weak_keyword and not is_question)  # "먹"은 질문이 아닐 때만 추천 트리거
            or (len(utterance.strip()) < 3 and casual_type == "chitchat")
        )

        if should_recommend:
            choice = r.recommend( # Use global r
                weather=actual_weather,
                mood=intent_data.get("mood"),
                meal_label=meal_label,
                is_late_evening=is_late_evening,
            )
            if choice:
                recommended_in_response = True
                session_manager.set_last_recommendation(user_id, choice)
                menu_response = (
                    await generate_response_with_gemini(
                        utterance, choice, intent_data, conversation_history, meal_label=meal_label
                    )
                    if (GEMINI_AVAILABLE_FOR_REQUEST and not _gemini_in_cooldown())
                    else generate_response_message(choice, intent_data, meal_label=meal_label)
                )
                response_text = (
                    f"{casual_response}\n\n오늘 {meal_label}은 이 메뉴 어떠세요?\n\n{menu_response}"
                )
                session_manager.add_conversation(user_id, "user", utterance, choice)
            else:
                response_text = casual_response
        else:
            response_text = casual_response
            session_manager.add_conversation(user_id, "user", utterance)
        session_manager.add_conversation(user_id, "bot", response_text)


    elif intent == "reject":
        last_rec = session_manager.get_last_recommendation(user_id)
        excluded = [last_rec["name"]] if last_rec and "name" in last_rec else []
        choice = r.recommend( # Use global r
            weather=actual_weather,
            cuisine_filters=intent_data.get("cuisine_filters"),
            mood=intent_data.get("mood"),
            excluded_menus=excluded,
            tag_filters=intent_data.get("tag_filters", []),
            meal_label=meal_label,
            is_late_evening=is_late_evening,
        )
        if choice:
            recommended_in_response = True
            session_manager.set_last_recommendation(user_id, choice)
            menu_res = (
                await generate_response_with_gemini(
                    utterance, choice, intent_data, conversation_history, meal_label=meal_label
                )
                if (GEMINI_AVAILABLE_FOR_REQUEST and not _gemini_in_cooldown())
                else generate_response_message(choice, intent_data, meal_label=meal_label)
            )
            response_text = f"알겠습니다! 다른 메뉴로 추천드릴게요 😊\n\n" + menu_res
            session_manager.add_conversation(user_id, "user", utterance, choice)
        else:
            response_text = "추천할 만한 다른 메뉴가 없어요 ㅠㅠ"
        session_manager.add_conversation(user_id, "bot", response_text)

    elif intent == "accept":
        last_rec = session_manager.get_last_recommendation(user_id)
        response_text = (
            f"좋은 선택이에요! {last_rec['name']} 맛있게 드세요~ 🍽️😊"
            if last_rec
            else f"{meal_label} 메뉴 추천해드릴까요? 😊"
        )
        session_manager.add_conversation(user_id, "user", utterance)
        session_manager.add_conversation(user_id, "bot", response_text)

    elif intent == "explain":
        last_rec = session_manager.get_last_recommendation(user_id)
        if last_rec:
            # Gemini가 가능하면 Gemini로, 아니면 로컬 설명 생성
            if GEMINI_AVAILABLE_FOR_REQUEST and not _gemini_in_cooldown():
                response_text = await generate_explanation_with_gemini(
                    utterance,
                    last_rec,
                    conversation_history,
                    weather=actual_weather,
                    mood=intent_data.get("mood"),
                )
            else:
                response_text = generate_explanation_fallback(last_rec, weather=actual_weather, mood=intent_data.get("mood"))
        else:
            response_text = "아직 추천해드린 메뉴가 없어요! 먼저 메뉴를 추천해드릴까요? 😊"
        
        session_manager.add_conversation(user_id, "user", utterance)
        session_manager.add_conversation(user_id, "bot", response_text)

    else:  # recommend
        weather = actual_weather or intent_data.get("weather")
        choice = r.recommend( # Use global r
            weather=weather,
            cuisine_filters=intent_data.get("cuisine_filters"),
            mood=intent_data.get("mood"),
            tag_filters=intent_data.get("tag_filters", []),
            meal_label=meal_label,
            is_late_evening=is_late_evening,
        )

        if choice:
            recommended_in_response = True
            session_manager.set_last_recommendation(user_id, choice)
            if GEMINI_AVAILABLE_FOR_REQUEST and not _gemini_in_cooldown():
                response_text = await generate_response_with_gemini(
                    utterance, choice, intent_data, conversation_history, meal_label=meal_label
                )
            else:
                response_text = generate_response_message(choice, intent_data, meal_label=meal_label)
            session_manager.add_conversation(user_id, "user", utterance, choice)
            session_manager.add_conversation(user_id, "bot", response_text)
        else:
            response_text = "추천할 만한 메뉴가 없어요 ㅠㅠ 조건을 바꿔보세요."

    # 6. 재시도 횟수에 따른 멘트 추가 (Sticky Retry Logic)
    retry_count = session.get("recommendation_count", 0)
    retry_prefix = ""
    
    if intent in ["recommend", "reject", "casual"]:
        # 추천이 포함된 응답일 때만 적용
        if "추천" in response_text or "어떠세요" in response_text:
            if retry_count == 4:
                retry_prefix = "도대체 뭘 잡숩고 싶으신 겁니까?\n\n"
            elif retry_count == 5:
                retry_prefix = "이럴 거면 왜 물어보세요?\n\n"
            elif retry_count >= 6:
                retry_prefix = "😭 저기요... 저도 이제 힘들어요... 그냥 아까 추천드린 것 중에 하나 드시죠! 마지막이에요!\n\n"
    
    if mismatch_notice and recommended_in_response:
        response_text = f"{mismatch_notice}\n\n{response_text}"

    final_text = f"{retry_prefix}{response_text}"

    # 7. Kakao Response 구성
    return get_final_kakao_response(final_text)


def build_varied_recommendation(choice: Dict, intent_data: Dict, meal_label: str = "점심") -> str:
    """천 가지 이상의 조합으로 자연스럽고 다양한 추천 멘트를 생성합니다 (Fallback용)."""
    import random
    name = choice.get('name', '추천 메뉴')
    area = choice.get('area', '회사 근처')
    
    # 1. 인사말 (12종)
    headers = [
        "음... 마스터님을 위해 열심히 골라봤어요! ✨",
        "제 생각엔 여기가 오늘 기분과 딱 맞는 것 같아요! 🤗",
        "고민 끝에 결정했습니다! 바로 여기예요. 🍱",
        "오늘은 왠지 이 메뉴가 마스터님을 부르는 것 같네요! 😋",
        "멀리 가지 마시고 여기서 드시는 건 어떨까요? 📍",
        "실패 없는 선택! 오늘은 이 메뉴 어떠세요? 👍",
        "마스터님이 좋아하실 만한 곳으로 찾아봤습니다! ✨",
        "기분 전환에 딱 좋은 메뉴를 발견했어요! 🌈",
        "든든한 한 끼를 위해 이곳을 추천드립니다! 💪",
        "오늘 같은 날씨엔 이런 메뉴가 진리죠! ⛅",
        "맛있는 한 끼! 여기를 강력 추천합니다! 🍽️",
        "고민 해결! 제가 대신 골라드렸습니다. 😎"
    ]
    
    # 2. 추천 본문 (15종)
    bodies = [
        f"오늘 {meal_label}은 **[{name}]** 어떠세요? {area}에 있어서 가깝답니다!",
        f"**[{name}]** 한 번 가보시는 걸 추천드려요! ({area})",
        f"**[{name}]** 이(가) 오늘 메뉴로 아주 좋을 것 같아요! {area}에 있네요.",
        f"**[{name}]** 어떨까요? {area} 라서 접근성도 최고입니다!",
        f"제 추천은 바로 **[{name}]** 입니다! 위치는 {area} 예요.",
        f"오늘 {meal_label}은 **[{name}]** 어떠신가요? {area} 에 위치해 있습니다!",
        f"마스터님께 딱 맞는 **[{name}]** 추천드립니다! ({area})",
        f"고민 말고 **[{name}]** 으로 고고! {area} 에 있어요.",
        f"**[{name}]** 에서 맛있는 한 끼 어떠세요? {area} 입니다!",
        f"오늘은 **[{name}]** 이(가) 정답인 것 같네요! ({area})",
        f"**[{name}]** 추천드려요! {area} 에 있어서 금방 가실 거예요.",
        f"후회 없는 선택! **[{name}]** 추천합니다! {area} 에 있어요.",
        f"**[{name}]** 이(가) 마스터님을 기다리고 있어요! ({area})",
        f"오늘은 **[{name}]** 으로 결정! {area} 에 있답니다.",
        f"마스터님의 맛있는 한 끼를 위해 **[{name}]** 준비해봤습니다! ({area})"
    ]
    
    # 3. 마무리 (10종)
    closers = [
        "분명 만족스러운 식사가 되실 거예요! 😊",
        "맛있게 드시고 힘찬 오후 보내세요! 🍽️",
        "든든하게 먹고 기분 좋게 시작해봐요! 💪",
        "제가 고른 만큼 정말 맛있을 겁니다! ✨",
        "맛있는 한 끼를 제가 응원합니다! 🤗",
        "오늘 하루도 화이팅이에요! 맛있는 식사 되세요! 🌈",
        "다녀오시면 리뷰 한 번 들려주세요! 😋",
        "실패 없는 한 끼, 제가 보장합니다! 👍",
        "즐겁게 식사하시고 오세요! 🍱",
        f"마스터님께 기쁨을 주는 {meal_label} 시간이 되길! ✨"
    ]
    
    return f"{random.choice(headers)}\n\n{random.choice(bodies)}\n\n{random.choice(closers)}"

def get_emergency_fallback_response(reason: str, utterance: str = "", user_id: str = "Master", weather: str = None) -> Dict:
    """타임아웃 또는 서버 에러 시 즉시 반환할 안전 응답 (글로벌 r 활용하여 초고속 생성)"""
    import random
    intent_data = {} # [FIX] UnboundLocalError 방지
    time_ctx = get_time_context(utterance)
    current_meal_label = time_ctx["current_label"] or "점심"
    requested_meal_label = time_ctx["requested_label"]
    is_late_evening = bool(time_ctx["is_late_evening"])
    meal_label = requested_meal_label or current_meal_label

    try:
        r.refresh_data()
        intent_data = analyze_intent_fallback(utterance)
        intent = intent_data.get("intent")
        logger.warning(f"🚨 Fallback Logic | Utterance: '{utterance}' | Detected Intent: '{intent}'")
        
        if weather: intent_data["weather"] = weather
        
        # [NEW] '이유(explain)' 물어봤는데 비상 모드인 경우
        if intent == "explain":
            last_rec = session_manager.get_last_recommendation(user_id)
            if last_rec:
                try:
                    # 마지막 추천이 있으면 그 이유를 설명해줌
                    explanation = generate_explanation_fallback(last_rec, weather=weather, mood=intent_data.get("mood"))
                    # [다양화] 설명 앞에 붙는 멘트도 랜덤화
                    prefixes = [
                        "아, 그 메뉴를 고른 이유요? 바로 이거예요! 👇\n\n",
                        "제가 왜 여길 골랐는지 궁금하시죠? ✨\n\n",
                        "마스터님을 위해 고민한 결과입니다! 👏\n\n",
                        "이런 특별한 이유가 있었답니다. 😊\n\n"
                    ]
                    
                    final_text = f"{random.choice(prefixes)}{explanation}"
                    
                    # [DEFENSIVE] 2001 에러 방지 (길이/내용 체크) - 카카오 제한 준수
                    if not final_text or len(final_text) > 400:
                        logger.warning(f"⚠️ Text too long or empty ({len(final_text)}): {final_text[:50]}...")
                        final_text = f"'{last_rec.get('name')}' 가보시면 절대 후회 안 하실 거예요! 믿고 드셔보세요. 👍"
                        
                    return get_final_kakao_response(final_text)
                    
                except Exception as ex:
                    logger.warning(f"🚨 Explain Gen Failed: {ex}")
                    return get_final_kakao_response(f"'{last_rec.get('name')}' 정말 맛있는 곳이라 추천드렸어요! 😊")
            else:
                # 추천 내역이 없으면 자연스럽게 추천으로 유도
                return get_final_kakao_response("아직 제가 아무것도 추천드리지 않았네요! 😊 맛있는 메뉴 하나 골라드릴까요?")

        # 추천 로직 (기존과 동일하지만 멘트 생성은 build_varied_recommendation 사용)
        fallback_menu = r.recommend(
            weather=intent_data.get("weather"),
            cuisine_filters=intent_data.get("cuisine_filters"),
            mood=intent_data.get("mood"),
            tag_filters=intent_data.get("tag_filters"),
            meal_label=meal_label,
            is_late_evening=is_late_evening,
        )
    except:
        fallback_menu = None

    if not fallback_menu:
        fallback_menu = random.choice(r.menus) if r.menus else {"name": "회사 근처 맛집", "area": "근처"}

    # [핵심] 조합형 엔진으로 멘트 다양화
    message = build_varied_recommendation(fallback_menu, intent_data, meal_label=meal_label)
    
    # [FIX] 세션에 추천 이력을 저장해야 "이유는?" 질문에 대답할 수 있음
    try:
        r.history_mgr.save_history(user_id, fallback_menu['name']) # 장기 기억 (중복 방지)
        session_manager.set_last_recommendation(user_id, fallback_menu) # 단기 기억 (문맥 대화)
    except:
        pass
        
    return get_final_kakao_response(message)


def get_help_response() -> Dict:
    """도움말 응답 (재사용 가능하도록 분리)"""
    text = (
        "🤖 **DDMC 점심 추천 봇 사용법**\n\n"
        "1️⃣ **메뉴 추천**: \"점심 추천\", \"비 오는데 뭐 먹지\", \"랜덤\"\n"
        "2️⃣ **이유/정보**: \"이유는?\", \"어디야?\", \"날씨 어때\"\n"
        "3️⃣ **기분 맞춤**: \"화났을 때 매운 거\", \"다이어트 메뉴\""
    )
    return get_final_kakao_response(text)


def get_final_kakao_response(text: str) -> Dict:
    """최종 카카오 응답 포맷팅"""
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": text}}],
            "quickReplies": [
                {"label": "🎲 랜덤 추천", "action": "message", "messageText": "랜덤 추천해줘"},
                {"label": "⛅ 날씨 맞춤", "action": "message", "messageText": "날씨에 맞게 추천해줘"},
                {"label": "❓ 도움말", "action": "message", "messageText": "도움말"},
            ],
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot_server:app", host="0.0.0.0", port=8000, reload=False)
