from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
import recommender
import os
import random
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

app = FastAPI()

# Gemini API 설정
try:
    import google.generativeai as genai
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        from google.generativeai.types import HarmCategory, HarmBlockThreshold

        genai.configure(api_key=GEMINI_API_KEY)
        
        # 안전 설정 (필터링 방지)
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        # Generation Configs
        INTENT_CONFIG = {
            "temperature": 0.1,
            "max_output_tokens": 100,
            "top_p": 0.8,
            "top_k": 40
        }
        
        RESPONSE_CONFIG = {
            "temperature": 0.85,
            "max_output_tokens": 200,
            "top_p": 0.8,
            "top_k": 40
        }

        # 기본 모델 (Response용)
        gemini_model = genai.GenerativeModel('gemini-2.0-flash', safety_settings=safety_settings, generation_config=RESPONSE_CONFIG)
        
        # Intent 분석용 모델
        intent_model = genai.GenerativeModel('gemini-2.0-flash', safety_settings=safety_settings, generation_config=INTENT_CONFIG)
        
        GEMINI_AVAILABLE = True
        print("✅ Gemini API 연동 성공!")
    else:
        GEMINI_AVAILABLE = False
        print("⚠️  GEMINI_API_KEY가 설정되지 않았습니다. 키워드 매칭 방식으로 작동합니다.")
except Exception as e:
    GEMINI_AVAILABLE = False
    print(f"⚠️  Gemini API 초기화 실패: {e}. 키워드 매칭 방식으로 작동합니다.")

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
    "화남": ["화나", "짜증", "열받", "스트레스", "매운", "빡쳐"],
    "행복": ["행복", "기분좋", "신나", "즐거", "월급"],
    "우울": ["우울", "슬퍼", "꿀꿀", "다운"],
    "플렉스": ["비싼", "고급", "법카", "플렉스", "월급", "보너스", "돈지랄"],
    "다이어트": ["다이어트", "살빼", "가벼운", "샐러드", "관리", "식단"]
}

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
INTENT_TIMEOUT_SEC = 3.5
GENERATION_TIMEOUT_SEC = 2.5

async def run_gemini_with_timeout(model, prompt: str, timeout_sec: float, log_label: str):
    """Execute Gemini call in a thread with a timeout and return text or None."""
    try:
        result = await asyncio.wait_for(asyncio.to_thread(model.generate_content, prompt), timeout=timeout_sec)
        return (result.text or "").strip()
    except asyncio.TimeoutError:
        print(f"{log_label} timeout after {timeout_sec}s")
    except Exception as e:
        print(f"{log_label} fail: {e}")
    return None

def format_history(conversation_history: List[Dict], limit: int = 2) -> str:
    """대화 히스토리 포맷팅 (토큰 절약)"""
    if not conversation_history:
        return ""
    return "\n".join([
        f"{h['role']}: {h['message']}"
        for h in conversation_history[-limit:]
    ])

async def analyze_intent_with_gemini(utterance: str, conversation_history: List[Dict]) -> Dict[str, Any]:
    """Gemini API를 사용하여 사용자 의도를 분석합니다. (Short Prompt + Strict Config)"""
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
        print(f"⚠️ Intent 분석 실패/타임아웃: {e}")
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
    if any(word in utterance_lower for word in ["안녕", "하이", "hello", "hi"]):
        intent = "casual"
        casual_type = "greeting"
    elif any(word in utterance_lower for word in ["고마", "감사", "thanks", "thank"]):
        intent = "casual"
        casual_type = "thanks"
    elif any(word in utterance_lower for word in ["왜", "이유", "why", "어째서", "이유는"]):
        intent = "explain"
    elif any(word in utterance_lower for word in ["싫", "별로", "다른", "아니", "no", "패스"]):
        intent = "reject"
    # recommend (명확한 키워드가 있을 때만 추천)
    elif any(word in utterance_lower for word in ["추천", "메뉴", "밥", "식사", "배고파", "뭐먹지", "골라줘", "아무거나", "랜덤", "알아서", "해봐", "해", "고"]):
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
            
    # [NEW] 음식 키워드가 발견되면 무조건 추천 Intent로 고정
    if (cuisine_filters or tag_filters) and intent != "reject":
        intent = "recommend"
    
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
    추천 이유 설명 기본 응답 (Context-Aware Fallback)
    """
    name_with_josa = get_josa(rec['name'], "은/는")
    
    import random
    
    tags = rec.get("tags", [])
    has_soup = "soup" in tags
    has_spicy = "spicy" in tags
    has_meat = "meat" in tags
    has_rice = "rice" in tags
    has_light = "light" in tags
    has_noodle = "noodle" in tags
    has_hot = "hot" in tags
    
    reasons = []
    
    # 1) 날씨 기반
    if weather in ["비", "장마", "흐림"] and has_soup:
        reasons.append("비 오는 날 뜨끈한 국물로 몸 녹이기 좋아서")
    elif weather in ["비", "장마", "흐림"]:
        reasons.append("비 오는 날 든든하게 드시라고")
        
    # [NEW] 비 오는 날 전용 팁 (사람 붐빔 경고)
    rain_tip = ""
    if weather in ["비", "장마"]:
        rain_tip = "\n\n💡 **Tip**: 비가 오니 실내가 평소보다 붐빌 것 같아요. 평소보다 조금 서둘러 가시는 걸 추천드려요! 🏃‍♂️"
    
    elif weather in ["눈", "추위", "겨울", "한파"] and (has_soup or has_hot):
        reasons.append("추운 날 따뜻하게 드시라고")
    elif weather == "한파" and rec.get('area') in ["회사 지하식당", "회사 1층"]:
        reasons.append("날씨가 영하니까 나가지 말고 안에서 드시라고")
    elif weather in ["더위", "여름"] and has_light:
        reasons.append("더운 날 부담 없이 시원하게 드시라고")
    elif weather in ["더위", "여름"] and has_noodle:
        reasons.append("더운 날 면 한 그릇으로 시원하게 하시라고")
    
    # 2) 기분 기반
    if mood in ["화남", "스트레스"]:
        if has_spicy:
            reasons.append("매운 거로 스트레스 한 번 확 풀라고")
        else:
            reasons.append("스트레스엔 든든한 한 끼가 최고라서")
    elif mood in ["우울", "슬픔"]:
        if has_soup or has_rice or has_meat:
            reasons.append("기분 전환에 도움 되게 든든한 걸로 골랐어요")
        else:
            reasons.append("우울할 땐 맛있는 게 약이라서")
    elif mood in ["피곤"]:
        if has_rice and has_meat:
            reasons.append("고기+밥 조합으로 에너지 채우시라고")
        else:
            reasons.append("지친 몸에 힘 나는 메뉴라서")
    elif mood == "행복":
        if has_meat:
            reasons.append("기분 좋은 날엔 맛있는 고기가 딱이라서")
    elif mood == "다이어트":
        if has_light:
            reasons.append("가볍게 관리하기 좋은 메뉴라서")
    elif mood == "플렉스":
        reasons.append("오늘은 제대로 flex 하시라고")
    
    # 3) 메뉴 특징 기반
    if not reasons:
        if has_soup:
            reasons.append("국물까지 시원/깔끔해서")
        if has_spicy and len(reasons) < 2:
            reasons.append("매콤하게 입맛 살리기 좋아서")
        if has_meat and len(reasons) < 2:
            reasons.append("고기가 푸짐해 든든해서")
        if has_light and len(reasons) < 2:
            reasons.append("가볍게 한 끼 하기 좋아서")
    
    # 4) 기본
    if not reasons:
        reasons = [
            "정말 맛있는 곳이라",
            "요즘 인기 있는 메뉴라",
            "실패 없는 선택이라",
            "많은 분들이 좋아하는 곳이라"
        ]
    
    reason = random.choice(reasons)
    return f"{name_with_josa} {reason} 추천드렸어요! 위치도 {rec.get('area')}라서 가기 좋답니다. 😊{rain_tip}"


async def generate_casual_response_with_gemini(utterance: str, casual_type: str, conversation_history: List[Dict]) -> str:
    """일상 대화 응답 (Short Prompt)"""
    history_text = format_history(conversation_history)
    
    prompt = f"""친근한 챗봇 응답:
히스토리:
{history_text}
사용자: {utterance}

가이드:
1. 친구처럼 밝고 공감하는 말투 (이모지 사용)
2. 사용자의 말에 맞춰 자연스럽게 대답 (억지로 점심 얘기 꺼내지 말 것)
3. 만약 사용자가 배고파하거나 점심 맥락일 때만 메뉴 추천 유도
4. 1-2문장으로 짧게

응답:"""
    
    response_text = await run_gemini_with_timeout(
        gemini_model, prompt, GENERATION_TIMEOUT_SEC, "Casual response"
    )
    if response_text:
        return response_text
    return generate_casual_response_fallback(casual_type)


def generate_casual_response_fallback(casual_type: str) -> str:
    """
    일상 대화 기본 응답 (Fallback)
    """
    if casual_type == "greeting":
        return "안녕하세요! 😊 점심 메뉴 고민되시나요? 추천해드릴게요!"
    elif casual_type == "thanks":
        return "천만에요! 맛있게 드세요~ 🍽️ 다음에도 점심 고민되시면 언제든 불러주세요!"
    else:
        # 야, 등 짧은 호출이나 잡담에 대한 대응
        messages = [
            "네! 점심 메뉴 고민이신가요? 🤔",
            "부르셨나요? 맛있는 점심 추천해드릴까요? 😋",
            "심심하신가요? 저랑 점심 메뉴 고르기 해요! 🎲",
            "네! 무슨 일이신가요? 배고프시면 '점심 추천'이라고 말해보세요!",
            "음... 글쎄요? 점심 메뉴 추천이라면 자신 있습니다! 😎",
            "무슨 말씀인지 잘 모르겠지만... 배고프신 건 아니죠? 밥이나 먹으러 가요! 🍚",
            "혹시 비밀번호 물어보신 거 아니죠? 🤐 (농담입니다)",
            "오늘 점심 뭐 드실까요? 제가 골라드릴게요! 🍽️",
            "배고프신가요? 맛집 추천해드릴게요! 😊",
            "점심 시간이네요! 어떤 메뉴 드시고 싶으세요? 🤗",
            "저를 부르셨나요? 점심 메뉴 고민 해결사 등장! 💪",
            "네네! 오늘도 맛있는 점심 찾아드릴게요! ✨",
            "무슨 일이신가요? 점심 추천이 필요하시면 말씀해주세요! 🙌"
        ]
        import random
        return random.choice(messages)


def build_emotion_prefix(intent_data: Dict) -> str:
    """감정/기분에 따라 멘트 앞머리 고정."""
    mood = intent_data.get("mood")
    emotion = intent_data.get("emotion")
    
    if mood == "화남":
        return "화 풀 땐 매콤하게! 🔥\n"
    if mood == "우울":
        return "기분 전환엔 든든하게! 🌈\n"
    if mood == "피곤":
        return "에너지 채우는 한 끼! 💪\n"
    if mood == "행복":
        return "기분 좋은 날엔 맛있는 걸로! 😊\n"
    if mood == "플렉스":
        return "오늘은 제대로 flex! 💳\n"
    if mood == "다이어트":
        return "가볍게 관리하는 날! 🥗\n"
    
    if emotion == "negative":
        return "힘든 날엔 든든하게! 🙏\n"
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
2. 위치 장점 언급
3. 친근한 말투, 이모지

응답:"""
    
    response_text = await run_gemini_with_timeout(
        gemini_model, prompt, GENERATION_TIMEOUT_SEC, "Explanation"
    )
    if response_text:
        return response_text
    return generate_explanation_fallback(last_recommendation, weather, mood)

async def generate_response_with_gemini(utterance: str, choice: dict, intent_data: Dict, conversation_history: List[Dict]) -> str:
    """추천 멘트 생성 (Short Prompt)"""
    name = choice['name']
    category = choice.get('category', '')
    area = choice.get('area', '')
    tags = choice.get('tags', [])
    
    context = f"상황: {intent_data.get('weather')}, {intent_data.get('mood')}, {intent_data.get('cuisine_filters')}"
    emotion = intent_data.get('emotion', 'neutral')
    tone = "위로하는 톤" if emotion == "negative" else "밝은 톤"
    prefix = build_emotion_prefix(intent_data)
    
    prompt = f"""점심 추천 멘트 작성 ({tone}):
사용자: "{utterance}"
메뉴: {name} ({category}, {area})
특징: {', '.join(tags)}
{context}

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
    return prefix + generate_response_message(choice, intent_data)


def generate_response_message(choice: dict, intent_data: Dict) -> str:
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
    emotion_prefix = build_emotion_prefix(intent_data)
    
    # 상황별 멘트
    import random
    
    # 상황별 멘트 리스트
    prefixes = []
    
    if emotion == "negative" and not emotion_prefix:
        prefixes = [
            "힘든 하루시네요 😔 든든하고 맛있는 걸로 기운 내세요! ",
            "저런... 😢 맛있는 거 먹고 털어버려요! ",
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
    elif mood == "피곤":
        prefixes = [
            "피곤할 땐 든든하게! 💪 ",
            "지친 몸엔 맛있는 밥이 보약! ",
            "에너지 충전 하세요! ⚡ "
        ]
    elif mood == "행복":
        prefixes = [
            "기분 좋은 날엔 맛있는 걸로! 😊 ",
            "오늘 같은 날은 파티죠! 🎉 ",
            "행복한 기분 그대로 맛있는 식사! "
        ]
    elif mood == "우울":
        prefixes = [
            "기분 전환이 필요하시군요! 🌈 ",
            "우울할 땐 맛있는 거 앞으로! ",
            "달달하거나 매콤한 거 어떠세요? "
        ]
    elif mood == "화남":
        prefixes = [
            "맛있는 거 먹고 풀어요! 😤 ",
            "스트레스엔 역시 먹는 거죠! 🔥 ",
            "매운 거나 맛있는 걸로 힐링해요! "
        ]
    
    # 비 오는 날 전용 팁
    rain_tip = ""
    if weather == "비":
        rain_tip = "\n\n💡 **Tip**: 비가 오면 실내가 평소보다 붐빌 수 있으니 조금 더 서둘러 가보세요! 🏃‍♂️"
    
    selected_prefix = random.choice(prefixes) if prefixes else ""
    
    return f"{emotion_prefix}{selected_prefix}추천드립니다: [{name}] 🍜\n\n📍 위치: {area}\n🍽️ 종류: {category}{rain_tip}"


@app.post("/api/lunch")
async def recommend_lunch(payload: SkillPayload):
    """
    KakaoTalk Skill Endpoint for Lunch Recommendation
    """
    # 1. 사용자 ID 추출
    user_id = payload.userRequest.user.id if payload.userRequest.user else "anonymous"
    utterance = payload.userRequest.utterance
    
    # =================================================================
    # 🕵️‍♂️ 이스터에그 (Easter Egg) 
    # =================================================================
    # "김형석", "만든사람" 등이 포함되면 찬양 모드 발동
    easter_egg_keywords = [
        "김형석", "만든사람", "만든 사람", "누가만듬", "개발자", "제작자",
        "누가만들", "누가했", "누구작품", "창조주", "주인장"
    ]
    
    if any(keyword in utterance.replace(" ", "") for keyword in easter_egg_keywords):
        import random
        
        # 찬양 문구 리스트 (여기만 수정하면 됨!)
        praise_messages = [
            # 버전 1: 과한 찬양 (기존)
            (
                "🌟 **시스템 경보: 위대한 창조주 감지!** 🌟\n\n"
                "앗! 당신은... 이 세상 모든 코드를 지배하고,\n"
                "점심 메뉴의 진리를 깨우치신 **김형석님**?! 🙇‍♂️\n\n"
                "저 같은 미천한 AI는 감히 흉내 낼 수 없는\n"
                "높은 안목과 센스를 가지신 분이죠! (찬양합니다 ✨)\n\n"
                "💡 **특별 정보**\n"
                "혹시 봇의 추천이 마음에 안 드시나요?\n"
                "지금 바로 **김형석님께 직접 연락**해보세요! 📞\n\n"
                "그분께서 친히 AI보다 100배 더 완벽하고\n"
                "개쩌는 메뉴를 하사해주실 겁니다! (아마도요? 😉)"
            ),
            # 버전 2: 신비주의 & 카리스마
            (
                "🕶️ **Top Secret Information**\n\n"
                "Code Name: **K.H.S (김형석)**\n"
                "Role: The Architect of Lunch (점심의 설계자)\n\n"
                "그분은 단순히 코드를 짜는 게 아닙니다.\n"
                "여러분의 '배고픔'을 해결하기 위해 이 알고리즘을 설계하셨죠.\n\n"
                "🤖 AI의 판단보다 더 정확한 추천을 원하시나요?\n"
                "그렇다면 **김형석님께 직접 DM**을 보내보세요.\n"
                "그분의 직관은 데이터보다 날카롭습니다. ⚡"
            ),
            # 버전 3: 유쾌 & 병맛
            (
                "🥘 **김형석** (a.k.a 점심 메뉴판의 지배자)\n\n"
                "이 봇을 누가 만들었냐고요?\n"
                "바로 **김형석**님입니다! (박수 짝짝짝 👏)\n\n"
                "그분으로 말할 것 같으면...\n"
                "눈 감고도 맛집을 찾아내고,\n"
                "숨만 쉬어도 메뉴가 떠오르는 **푸드 마스터**시죠.\n\n"
                "📢 **꿀팁 대방출**\n"
                "저(AI) 말고 진짜배기 추천이 필요하다면?\n"
                "**김형석님께 카톡** 하나 날려보세요.\n"
                "\"오늘 뭐 먹죠?\"라고 묻는 순간, 인생 메뉴가 나옵니다. 😋"
            )
        ]
        
        selected_message = random.choice(praise_messages)
        
        return {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "simpleText": {
                            "text": selected_message
                        }
                    }
                ]
            }
        }
    # =================================================================
    
    # 2. Rate Limiting 체크
    is_allowed, deny_reason = rate_limiter.is_allowed(user_id)
    if not is_allowed:
        return {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": f"⚠️ {deny_reason}"}}]
            }
        }
    


    # =================================================================

    # 3. 세션 가져오기
    session = session_manager.get_session(user_id)
    conversation_history = session_manager.get_conversation_history(user_id)
    
    # 3.5. 실제 날씨 가져오기 (캐시 사용)
    actual_weather = None
    now = datetime.now()
    
    # 캐시가 10분 이내면 재사용
    if weather_cache["last_updated"] and (now - weather_cache["last_updated"]) < timedelta(minutes=10):
        actual_weather = weather_cache["mapped_weather"]
        print(f"날씨 캐시 사용: {weather_cache['condition']} {weather_cache['temp']} → {actual_weather}")
    else:
        # 캐시 만료 또는 없음 - 새로 가져오기
        try:
            r = recommender.LunchRecommender()
            current_weather_condition, current_temp = r.get_weather()
            
            # 날씨 상태를 우리 키워드로 매핑
            weather_mapping = {
                "비": "비",
                "rain": "비",
                "rainy": "비",
                "눈": "눈",
                "snow": "눈",
                "snowy": "눈",
                "맑음": "맑음",
                "clear": "맑음",
                "cloudy": "흐림",
                "구름": "흐림"
            }
            
            # 온도로 추위/더위 판단
            if current_weather_condition:
                weather_lower = current_weather_condition.lower()
                for key, value in weather_mapping.items():
                    if key in weather_lower:
                        actual_weather = value
                        break
            
            # 온도 기반 판단 (날씨 상태가 없으면)
            if not actual_weather and current_temp:
                try:
                    temp_value = float(current_temp.replace("°C", "").replace("℃", "").strip())
                    if temp_value < 0:
                        actual_weather = "한파"
                    elif temp_value < 10:
                        actual_weather = "추위"
                    elif temp_value > 28:
                        actual_weather = "더위"
                except:
                    pass
            
            # 캐시 업데이트
            weather_cache["condition"] = current_weather_condition
            weather_cache["temp"] = current_temp
            weather_cache["mapped_weather"] = actual_weather
            weather_cache["last_updated"] = now
            
            print(f"날씨 새로 가져옴: {current_weather_condition} {current_temp} → {actual_weather}")
        except Exception as e:
            print(f"날씨 가져오기 실패: {e}, 캐시 사용 또는 스킵")
            actual_weather = weather_cache.get("mapped_weather")  # 이전 캐시라도 사용
    
    # 4. 의도 분석 (Hybrid: Simple Regex First -> Gemini Fallback)
    # 단순/명확한 키워드는 정규식으로 처리하여 속도 및 API 사용량 절약
    
    # 4.1 "날씨" 질문 단독 처리 (Gemini 불필요)
    if "날씨" in utterance and len(utterance) < 10 and not any(k in utterance for k in ["추천", "메뉴", "점심", "밥"]):
        r = recommender.LunchRecommender()
        cond, temp = r.get_weather()
        
        cond_display = cond if cond else "정보 없음"
        temp_display = temp if temp else "정보 없음"
        
        response_text = f"🌡️ 현재 날씨 정보\n\n상태: {cond_display}\n기온: {temp_display}\n\n날씨에 맞는 점심 추천해드릴까요? 😊"
        
        session_manager.add_conversation(user_id, "user", utterance)
        session_manager.add_conversation(user_id, "bot", response_text)
        
        return {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": response_text}}],
                "quickReplies": [{"label": "☔ 날씨에 맞게 추천", "action": "message", "messageText": "날씨에 맞게 추천해줘"}]
            }
        }

    # 4.2 명확한 키워드가 있는 경우 -> Regex 엔진 사용 (Fast Track)
    # (복잡한 문장이나 감정 표현이 섞인 경우는 Gemini로 넘김)
    utterance_lower = utterance.lower()
    is_help_request = any(k in utterance_lower for k in ["도움", "도움말", "사용법", "설명", "help", "어떻게", "기능"])
    is_simple_request = len(utterance) < 15 and any(k in utterance for k in ["추천", "메뉴", "점심", "밥", "뭐먹", "배고파", "랜덤"])
    
    # Fast Track: 도움말/단순 요청이면 LLM 건너뛰기
    if is_help_request:
        print("⚡ Fast Track: Help Request")
        intent_data = analyze_intent_fallback(utterance)
        GEMINI_AVAILABLE_FOR_REQUEST = False
    elif is_simple_request:
        print("⚡ Fast Track: Skipping Gemini (Simple Request)")
        intent_data = analyze_intent_fallback(utterance)
        # Fast Track에서는 응답 생성도 Fallback(Template) 사용 강제
        GEMINI_AVAILABLE_FOR_REQUEST = False 
    elif not GEMINI_AVAILABLE:
        print("⚡ Fallback: Gemini Not Available")
        intent_data = analyze_intent_fallback(utterance)
        GEMINI_AVAILABLE_FOR_REQUEST = False
    else:
        # 복잡한 문장 -> Gemini 사용
        intent_data = await analyze_intent_with_gemini(utterance, conversation_history)
        GEMINI_AVAILABLE_FOR_REQUEST = True
    
    intent = intent_data.get("intent", "recommend")
    casual_type = intent_data.get("casual_type")
    
    print(f"User: {user_id} | Intent: {intent} | Utterance: '{utterance}' | Engine: {'Regex' if is_simple_request else 'Gemini'}")
    
    # 5. 의도별 처리
    response_text = ""

    # =================================================================
    # ❓ 도움말 처리 (위치 이동: intent data 분석 후)
    # =================================================================
    if intent == "help":
         import random  # 퀵 리플라이에서 random.choice() 사용하기 위해 필요
         return {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "simpleText": {
                            "text": (
                                "🤖 **DDMC 점심 추천 봇 사용법**\n\n"
                                "1️⃣ **메뉴 추천**\n"
                                "- \"점심 추천\"\n"
                                "- \"비 오는데 뭐 먹지\"\n"
                                "- \"랜덤\"\n\n"
                                "2️⃣ **이유/정보**\n"
                                "- \"이유는?\"\n"
                                "- \"어디야?\"\n"
                                "- \"날씨 어때\"\n\n"
                                "3️⃣ **기분 맞춤**\n"
                                "- \"화났을 때 매운 거\"\n"
                                "- \"피곤한데 든든한 거\"\n"
                                "- \"다이어트 메뉴\"\n"
                            )
                        }
                    }
                ],
                "quickReplies": [
                    {
                        "label": "🎲 랜덤 추천",
                        "action": "message",
                        "messageText": "랜덤"
                    },
                    random.choice([
                        {"label": "🔥 매운 거", "action": "message", "messageText": "매운 거"},
                        {"label": "☔ 날씨 맞춤", "action": "message", "messageText": "날씨에 맞게"},
                        {"label": "💪 든든한 거", "action": "message", "messageText": "든든한 거"},
                        {"label": "🥗 다이어트", "action": "message", "messageText": "다이어트"},
                        {"label": "🍜 국물 요리", "action": "message", "messageText": "국물 요리"}
                    ])
                ]
            }
        }
    # =================================================================
    
    if intent == "casual":
        # 일상 대화
        if GEMINI_AVAILABLE_FOR_REQUEST:
            casual_response = await generate_casual_response_with_gemini(utterance, casual_type, conversation_history)
        else:
            casual_response = generate_casual_response_fallback(casual_type)
        
        # 점심 관련 키워드가 있거나, 짧은 입력(".") 일 때만 자동 추천
        # 점심 관련 키워드가 있거나, 짧은 입력(".") 일 때만 자동 추천
        # 단, 질문형("?")이거나 "냐", "까"로 끝나는 경우(의견 묻기)는 단순 잡담으로 처리 (추천 강요 X)
        is_question = any(utterance.strip().endswith(m) for m in ["?", "냐", "까", "니", "요", "죠"])
        has_strong_keyword = any(word in utterance.lower() for word in ["점심", "추천", "메뉴", "배고", "식사"])
        has_weak_keyword = "먹" in utterance.lower()
        
        should_recommend = (
            (has_strong_keyword) or 
            (has_weak_keyword and not is_question) or # "먹"은 질문이 아닐 때만 추천 트리거
            (len(utterance.strip()) < 3 and casual_type == "chitchat")
        )
        
        if should_recommend:
            # 날씨 기반 자동 추천 추가
            params = payload.action.params
            weather = params.get("weather") or intent_data.get("weather")
            mood = params.get("mood") or intent_data.get("mood")
            
            r = recommender.LunchRecommender()
            choice = r.recommend(weather=weather, mood=mood)
            
            if choice:
                session_manager.set_last_recommendation(user_id, choice)
                # 일상 대화 + 추천 결합
                if GEMINI_AVAILABLE_FOR_REQUEST:
                    menu_response = await generate_response_with_gemini(utterance, choice, intent_data, conversation_history)
                else:
                    menu_response = generate_response_message(choice, intent_data)
                response_text = f"{casual_response}\n\n그나저나 점심은 드셨어요? 오늘은 이 메뉴 어떠세요?\n\n{menu_response}"
                session_manager.add_conversation(user_id, "user", utterance, choice)
            else:
                response_text = casual_response
                session_manager.add_conversation(user_id, "user", utterance)
        else:
            # 일반 질문은 대화만
            response_text = casual_response
            session_manager.add_conversation(user_id, "user", utterance)
        
        session_manager.add_conversation(user_id, "bot", response_text)
    
    elif intent == "explain":
        # 추천 이유 설명
        last_rec = session_manager.get_last_recommendation(user_id)
        if last_rec:
            # 실제 날씨 우선
            weather = actual_weather or intent_data.get("weather")
            mood = intent_data.get("mood")
            
            if GEMINI_AVAILABLE_FOR_REQUEST:
                response_text = await generate_explanation_with_gemini(utterance, last_rec, conversation_history, weather, mood)
            else:
                response_text = generate_explanation_fallback(last_rec, weather, mood)
        else:
            response_text = "아직 추천드린 메뉴가 없어요. 점심 추천해드릴까요? 😊"
        session_manager.add_conversation(user_id, "user", utterance)
        session_manager.add_conversation(user_id, "bot", response_text)
    
    elif intent == "reject":
        # 추천 거부 - 다른 메뉴 추천 (이전 추천 제외)
        last_rec = session_manager.get_last_recommendation(user_id)
        excluded_menus = []
        if last_rec and 'name' in last_rec:
            excluded_menus.append(last_rec['name'])
        
        params = payload.action.params
        weather = params.get("weather") or intent_data.get("weather")
        mood = params.get("mood") or intent_data.get("mood")
        # cuisine_filters = intent_data.get("cuisine_filters") or None # 기존 라인 제거
        # [NEW] 태그 필터도 전달
        tag_filters = intent_data.get('tag_filters', [])
        
        if intent_data.get("cuisine_filters") or tag_filters:
            print(f"필터 적용: {intent_data.get('cuisine_filters')}, 태그: {tag_filters}")
        
        r = recommender.LunchRecommender()
        choice = r.recommend(weather=actual_weather, cuisine_filters=intent_data.get("cuisine_filters"), mood=intent_data.get("mood"), excluded_menus=excluded_menus, tag_filters=tag_filters)
        
        # (이전 추천과 같으면 다시 시도 로직은 recommend 내부 excluded_menus로 해결됨)
        
        if choice:
            session_manager.set_last_recommendation(user_id, choice)
            if GEMINI_AVAILABLE_FOR_REQUEST:
                response_text = f"알겠습니다! 그럼 다른 메뉴로 추천드릴게요 😊\n\n" + await generate_response_with_gemini(utterance, choice, intent_data, conversation_history)
            else:
                response_text = f"알겠습니다! 그럼 다른 메뉴로 추천드릴게요 😊\n\n" + generate_response_message(choice, intent_data)
            session_manager.add_conversation(user_id, "user", utterance, choice)
            session_manager.add_conversation(user_id, "bot", response_text)
        else:
            response_text = "추천할 만한 다른 메뉴가 없어요 ㅠㅠ"
    
    elif intent == "accept":
        # 추천 수락
        last_rec = session_manager.get_last_recommendation(user_id)
        if last_rec:
            response_text = f"좋은 선택이에요! {last_rec['name']} 맛있게 드세요~ 🍽️😊"
        else:
            response_text = "점심 메뉴 추천해드릴까요? 😊"
        session_manager.add_conversation(user_id, "user", utterance)
        session_manager.add_conversation(user_id, "bot", response_text)
    
    else:  # recommend
        # 점심 추천
        params = payload.action.params
        # 실제 날씨 우선, 사용자 입력은 보조
        weather = actual_weather or params.get("weather") or intent_data.get("weather")
        mood = params.get("mood") or intent_data.get("mood")
        cuisine_filters = intent_data.get("cuisine_filters") or None
        
        r = recommender.LunchRecommender()
        # [NEW] 태그 필터 추출 및 적용
        tag_filters = intent_data.get('tag_filters', [])
        choice = r.recommend(weather=weather, cuisine_filters=cuisine_filters, mood=mood, tag_filters=tag_filters)
        
        if choice:
            session_manager.set_last_recommendation(user_id, choice)
            if GEMINI_AVAILABLE_FOR_REQUEST:
                response_text = await generate_response_with_gemini(utterance, choice, intent_data, conversation_history)
            else:
                response_text = generate_response_message(choice, intent_data)
            session_manager.add_conversation(user_id, "user", utterance, choice)
            session_manager.add_conversation(user_id, "bot", response_text)
        else:
            response_text = "추천할 만한 메뉴가 없어요 ㅠㅠ 조건을 바꿔보세요."
    
    # 6. Kakao Skill Response 구성
    response = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": response_text
                    }
                }
            ]
        }
    }
    
    # -----------------------------------------------------------------
    # (공통) 모든 응답에 '바로가기 버튼(Quick Reply)' 붙이기 Update
    # -----------------------------------------------------------------
    # 리치 메뉴(고정 메뉴) 도입으로 인해 화면을 깔끔하게 유지하기 위해 
    # 기본 퀵 리플라이는 제거합니다. (필요 시에만 개별 추가)
    
    return response

if __name__ == "__main__":
    uvicorn.run("bot_server:app", host="0.0.0.0", port=8000, reload=False) # 운영 시 reload=False 권장
