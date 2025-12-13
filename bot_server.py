from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uvicorn
import recommender
import os
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
        
        gemini_model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety_settings)
        
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
    "추위": ["추워", "춥", "겨울", "한파", "추운", "쌀쌀"]
}

MOOD_KEYWORDS = {
    "피곤": ["피곤", "힘들", "지쳐", "졸려", "피로"],
    "행복": ["행복", "기분좋", "신나", "즐거", "좋아"],
    "우울": ["우울", "슬퍼", "기분안좋", "울적"],
    "화남": ["화나", "짜증", "열받", "빡쳐"]
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


def analyze_intent_with_gemini(utterance: str, conversation_history: List[Dict]) -> Dict[str, Any]:
    """
    Gemini API를 사용하여 사용자 의도를 분석합니다.
    """
    try:
        # 대화 히스토리 포맷팅
        history_text = "\n".join([
            f"{h['role']}: {h['message']}"
            for h in conversation_history[-3:]  # 최근 3개만
        ]) if conversation_history else "(첫 대화)"
        
        prompt = f"""다음 사용자 메시지와 대화 히스토리를 분석하여 JSON 형식으로 응답해주세요:

대화 히스토리:
{history_text}

현재 사용자 메시지: "{utterance}"

**현재 날짜/시간:** 2025년 12월 14일 오전 1시 (겨울, 추운 날씨)

다음 정보를 추출하세요:
1. intent: 사용자 발화의 **핵심 의도**를 파악하여 다음 중 하나로 분류하세요.
   * **recommend**: 점심/메뉴 추천을 원하는 모든 경우
     - 예: "점심 추천", "배고파", "뭐 먹지", "결정해줘", "메뉴 골라줘" 등
   * **explain**: 방금 추천받은 메뉴에 대해 더 알고 싶거나, 이유를 묻는 모든 경우
     - 예: "왜?", "이유는?", "근거가 뭐야?", "맛있어?", "어떤 맛이야?", "그게 뭔데?" 등
   * **reject**: 추천받은 메뉴가 마음에 들지 않거나, 다른 것을 원하는 모든 경우
     - 예: "싫어", "별로", "다른거", "노맛", "패스", "안 땡겨", "어제 먹음", "좆같네" 등 (비속어 포함 부정)
   * **accept**: 추천받은 메뉴에 대해 긍정적이거나, 수락하는 모든 경우
     - 예: "좋아", "콜", "진행시켜", "맛있겠다", "그걸로 할게", "ㅇㅇ", "오키", "좆잘은데", "개좋음" 등 (비속어 포함 긍정)
   * **casual**: 추천이나 메뉴와 직접 관련 없는 일상적인 대화, 인사, 감정 표현
     - 예: "안녕", "심심해", "너 누구야", "바보", "사랑해", "날씨 춥다" 등
   
   **판단 기준:** 
   - 사용자가 **추천에 대해 반응**하고 있다면 (수락/거절/질문) casual이 아닙니다.
   - 단어가 사전에 없더라도 **문맥상 의도**가 확실하면 해당 intent로 분류하세요.

2. casual_type: casual인 경우 세부 유형 ("greeting", "thanks", "chitchat", null)
3. emotion: 사용자의 감정 상태 ("negative", "neutral", "positive")
   - 비속어가 있어도 '좋다'는 의미면 positive입니다. (예: "존나 맛있겠다")
4. cuisine_filters: 언급된 음식 종류 (한식, 중식, 일식, 양식, 분식 리스트)
5. weather: 날씨 키워드 (비, 눈, 더위, 추위, null)
   - 명시적 언급: "비 오는 날", "눈 오는 날" 등
   - **추론:** "날씨에 맞는", "오늘 날씨" 등 → 현재 계절/날짜 고려하여 "추위" 추론
6. mood: 기분 키워드 (피곤, 행복, 우울, 화남, null)

JSON 형식으로만 응답하세요.
예시: {{"intent": "recommend", "casual_type": null, "emotion": "neutral", "cuisine_filters": ["한식"], "weather": "비", "mood": null}}"""

        response = gemini_model.generate_content(prompt)
        result_text = response.text.strip()
        
        # JSON 파싱
        import json
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
            
        result = json.loads(result_text)
        return result
        
    except Exception as e:
        print(f"Gemini 의도 분석 실패: {e}, 키워드 매칭으로 fallback")
        return analyze_intent_fallback(utterance)


def analyze_intent_fallback(utterance: str) -> Dict[str, Any]:
    """
    키워드 매칭으로 사용자 의도를 분석합니다 (Fallback).
    """
    utterance_lower = utterance.lower()
    
    # 의도 분석
    intent = "recommend"  # 기본값
    casual_type = None
    
    # 일상 대화 패턴
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
    # 긍정 피드백 패턴 (Fallback용 - 기본적인 것만)
    elif any(word in utterance_lower for word in ["좋", "맛있", "거기", "그거", "먹을", "ok", "yes", "굿"]):
        intent = "accept"
    # 일반 질문 패턴 (점심 추천 X)
    elif any(word in utterance_lower for word in ["날씨", "어때", "뭐해", "심심"]) and not any(word in utterance_lower for word in ["점심", "추천", "메뉴", "먹"]):
        intent = "casual"
        casual_type = "chitchat"
    elif len(utterance_lower) < 5 and not any(word in utterance_lower for word in ["점심", "추천", "메뉴", "먹"]):
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
        "mood": mood
    }


def generate_casual_response_with_gemini(utterance: str, casual_type: str, conversation_history: List[Dict]) -> str:
    """
    Gemini API를 사용하여 일상 대화 응답을 생성합니다.
    """
    try:
        history_text = "\n".join([
            f"{h['role']}: {h['message']}"
            for h in conversation_history[-3:]
        ]) if conversation_history else ""
        
        prompt = f"""당신은 친근한 점심 추천 챗봇입니다.

대화 히스토리:
{history_text}

사용자: {utterance}

위 메시지에 자연스럽게 응답하되, 대화를 점심 추천으로 자연스럽게 유도해주세요.
- 친근하고 밝은 톤으로 작성
- 이모지 적절히 사용
- 2-3문장으로 간결하게
- 점심 추천 서비스임을 자연스럽게 언급

응답:"""
        
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini 일상 대화 응답 생성 실패: {e}")
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
        return "저는 점심 추천 챗봇이에요! 😄 오늘 점심 뭐 드실지 추천해드릴까요?"


def generate_explanation_with_gemini(utterance: str, last_recommendation: Dict, conversation_history: List[Dict], weather: Optional[str] = None, mood: Optional[str] = None) -> str:
    """
    Gemini API를 사용하여 추천 이유를 설명합니다.
    """
    try:
        name = last_recommendation['name']
        category = last_recommendation.get('category', '')
        area = last_recommendation.get('area', '')
        tags = last_recommendation.get('tags', [])
        
        # 태그를 한글로 변환
        tag_descriptions = {
            'soup': '국물 요리',
            'hot': '따뜻한 음식',
            'noodle': '면 요리',
            'spicy': '매운 음식',
            'heavy': '든든한 음식',
            'light': '가벼운 음식',
            'meat': '고기 요리',
            'rice': '밥 요리'
        }
        tag_list = [tag_descriptions.get(tag, tag) for tag in tags]
        
        # 날씨/기분 정보
        weather_kr = {
            "비": "비 오는 날씨",
            "눈": "눈 오는 날씨",
            "더위": "더운 날씨",
            "추위": "추운 날씨"
        }
        mood_kr = {
            "피곤": "피곤한 상태",
            "행복": "기분 좋은 상태",
            "우울": "우울한 기분",
            "화남": "화난 상태"
        }
        
        context_parts = []
        if weather:
            context_parts.append(f"날씨: {weather_kr.get(weather, weather)}")
        if mood:
            context_parts.append(f"사용자 기분: {mood_kr.get(mood, mood)}")
        
        context_info = "\n".join(context_parts) if context_parts else "특별한 상황 정보 없음"
        
        # 대화 히스토리
        history_context = ""
        if conversation_history:
            recent_messages = conversation_history[-3:]
            history_context = "최근 대화:\n" + "\n".join([
                f"- {h['role']}: {h['message']}"
                for h in recent_messages
            ])
        
        prompt = f"""당신은 친근한 점심 추천 챗봇입니다.

{history_context}

사용자가 방금 추천받은 메뉴에 대해 "{utterance}"라고 물어봤습니다.

추천한 메뉴:
- 이름: {name}
- 종류: {category}
- 위치: {area}
- 특징: {', '.join(tag_list) if tag_list else '맛있는 메뉴'}

추천 시 고려한 상황:
{context_info}

**당신의 역할:**
이 메뉴를 왜 추천했는지 자연스럽고 설득력 있게 설명해주세요.

**가이드라인:**
1. 메뉴의 실제 특징을 구체적으로 언급 (예: "국물이 진하고 칼칼해서", "고기가 부드러워서")
2. **날씨나 기분을 고려했다면 반드시 언급** (예: "비 오는 날씨에 따뜻한 국물이 좋아서", "피곤하실 때 든든한 게 필요해서")
3. 위치의 장점 활용 (예: "{area}에 있어서 가깝고 편해요")
4. 친근하고 자연스러운 대화체로 작성
5. 3-5문장 정도로 설명
6. 이모지 적절히 사용
7. **가끔(50% 확률) 솔직하거나 재미있는 이유 덧붙이기 (랜덤 선택)**
   - "솔직히 제가 지금 먹고 싶어서 추천했어요 😋"
   - "개발자 김형석님이 좋아하는 메뉴라서 추천드려요!"
   - "이거 진짜 맛있으니까 꼭 드셔보세요 😉"
   - "그냥 제 느낌이 이 메뉴라고 하네요!"

**금지사항:**
- "맛있어서", "인기 있어서" 같은 추상적 표현만 쓰지 말 것
- **"든든하게"라는 표현 반복 금지 (다른 표현: 힘이 나는, 속이 편한, 알찬, 푸짐한 등)**
- 딱딱한 나열식 설명 금지
- 형식에 얽매이지 말고 자유롭게 대화하듯 설명

응답:"""
        
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini 설명 생성 실패: {e}")
        # Fallback
        name = last_recommendation['name']
        category = last_recommendation.get('category', '')
        area = last_recommendation.get('area', '')
        tags = last_recommendation.get('tags', [])
        
        tag_descriptions = {
            'soup': '국물 요리',
            'hot': '따뜻한 음식',
            'noodle': '면 요리',
            'spicy': '매운 음식',
            'heavy': '든든한 음식',
            'light': '가벼운 음식',
            'meat': '고기 요리',
            'rice': '밥 요리'
        }
        tag_list = [tag_descriptions.get(tag, tag) for tag in tags]
        
        reason_parts = []
        if weather:
            weather_reasons = {
                "비": "비 오는 날씨에 따뜻한 음식이 좋아서",
                "눈": "눈 오는 날씨에 따뜻하게 드실 수 있어서",
                "더위": "더운 날씨에 시원하게 드실 수 있어서",
                "추위": "추운 날씨에 따뜻하게 드실 수 있어서"
            }
            if weather in weather_reasons:
                reason_parts.append(weather_reasons[weather])
        
        if mood:
            mood_reasons = {
                "피곤": "피곤하실 때 든든하게 드실 수 있어서",
                "행복": "기분 좋은 날에 맛있게 드실 수 있어서",
                "우울": "기분 전환에 좋아서",
                "화남": "스트레스 해소에 좋아서"
            }
            if mood in mood_reasons:
                reason_parts.append(mood_reasons[mood])
        
        if tag_list:
            # 태그별 다양한 수식어 랜덤 선택
            import random
            descriptors = [
                f"{tag_list[0]}라서 호불호 없이 즐길 수 있어서",
                f"{tag_list[0]} 메뉴가 당기실 것 같아서",
                f"오늘 같은 날 {tag_list[0]} 한 끼가 딱이라서",
                f"{tag_list[0]} 좋아하시면 만족하실 거라서",
                f"{tag_list[0]}로 에너지 충전하시라고"
            ]
            reason_parts.append(random.choice(descriptors))
        if area:
            reason_parts.append(f"{area}에 위치해 있어서 접근성이 좋아서")
        
        if not reason_parts:
            reason_parts.append("점심시간에 딱 맞는 메뉴라서")
        
        return f"""{name}을(를) 추천한 이유는 {', '.join(reason_parts)}예요! 😊"""
    """
    Gemini API를 사용하여 추천 이유를 설명합니다.
    """
    try:
        name = last_recommendation['name']
        category = last_recommendation.get('category', '')
        area = last_recommendation.get('area', '')
        tags = last_recommendation.get('tags', [])
        
        # 태그를 한글로 변환
        tag_descriptions = {
            'soup': '국물 요리',
            'hot': '따뜻한 음식',
            'noodle': '면 요리',
            'spicy': '매운 음식',
            'heavy': '든든한 음식',
            'light': '가벼운 음식',
            'meat': '고기 요리',
            'rice': '밥 요리'
        }
        tag_list = [tag_descriptions.get(tag, tag) for tag in tags]
        
        # 대화 히스토리
        history_context = ""
        if conversation_history:
            recent_messages = conversation_history[-3:]
            history_context = "최근 대화:\n" + "\n".join([
                f"- {h['role']}: {h['message']}"
                for h in recent_messages
            ])
        
        prompt = f"""당신은 친근한 점심 추천 챗봇입니다.

{history_context}

사용자가 방금 추천받은 메뉴에 대해 "{utterance}"라고 물어봤습니다.

추천한 메뉴:
- 이름: {name}
- 종류: {category}
- 위치: {area}
- 특징: {', '.join(tag_list) if tag_list else '맛있는 메뉴'}

**당신의 역할:**
이 메뉴를 왜 추천했는지 자연스럽고 설득력 있게 설명해주세요.

**가이드라인:**
1. 메뉴의 실제 특징을 구체적으로 언급 (예: "국물이 진하고 칼칼해서", "고기가 부드러워서")
2. 위치의 장점 활용 (예: "{area}에 있어서 가깝고 편해요")
3. 상황에 맞는 이유 추가 (날씨, 시간대, 점심 메뉴로 적합한 이유 등)
4. 친근하고 자연스러운 대화체로 작성
5. 3-5문장 정도로 설명
6. 이모지 적절히 사용

**금지사항:**
- "맛있어서", "인기 있어서" 같은 추상적 표현만 쓰지 말 것
- 딱딱한 나열식 설명 금지
- 형식에 얽매이지 말고 자유롭게 대화하듯 설명

응답:"""
        
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini 설명 생성 실패: {e}")
        # Fallback
        name = last_recommendation['name']
        category = last_recommendation.get('category', '')
        area = last_recommendation.get('area', '')
        tags = last_recommendation.get('tags', [])
        
        tag_descriptions = {
            'soup': '국물 요리',
            'hot': '따뜻한 음식',
            'noodle': '면 요리',
            'spicy': '매운 음식',
            'heavy': '든든한 음식',
            'light': '가벼운 음식',
            'meat': '고기 요리',
            'rice': '밥 요리'
        }
        tag_list = [tag_descriptions.get(tag, tag) for tag in tags]
        
        reason_parts = []
        if tag_list:
            reason_parts.append(f"{tag_list[0]}라서 든든하게 드실 수 있어요")
        if area:
            reason_parts.append(f"{area}에 위치해 있어서 접근성이 좋아요")
        reason_parts.append("점심시간에 딱 맞는 메뉴예요")
        
        return f"""{name}을(를) 추천한 이유는 {', '.join(reason_parts)}! 😊"""


def generate_response_with_gemini(utterance: str, choice: dict, intent_data: Dict, conversation_history: List[Dict]) -> str:
    """
    Gemini API를 사용하여 자연스러운 추천 응답을 생성합니다.
    """
    try:
        name = choice['name']
        category = choice.get('category', '')
        area = choice.get('area', '')
        tags = choice.get('tags', [])
        
        cuisine_filters = intent_data.get('cuisine_filters', [])
        weather = intent_data.get('weather')
        mood = intent_data.get('mood')
        emotion = intent_data.get('emotion', 'neutral')
        
        # 대화 히스토리 포맷팅
        history_text = "\n".join([
            f"{h['role']}: {h['message']}"
            for h in conversation_history[-2:]
        ]) if conversation_history else ""
        
        # 태그를 한글로 변환
        tag_descriptions = {
            'soup': '국물 요리',
            'hot': '따뜻한 음식',
            'noodle': '면 요리',
            'spicy': '매운 음식',
            'heavy': '든든한 음식',
            'light': '가벼운 음식',
            'meat': '고기 요리',
            'rice': '밥 요리'
        }
        tag_list = [tag_descriptions.get(tag, tag) for tag in tags]
        
        emotion_context = ""
        if emotion == "negative":
            emotion_context = "사용자가 힘들어하거나 기분이 안 좋은 상태입니다. 공감하고 위로하는 톤으로 작성하세요."
        elif emotion == "positive":
            emotion_context = "사용자가 기분이 좋은 상태입니다. 밝고 즐거운 톤으로 작성하세요."
        
        prompt = f"""당신은 친근한 점심 추천 챗봇입니다.

대화 히스토리:
{history_text}

사용자 메시지: "{utterance}"

추천 메뉴:
- 이름: {name}
- 종류: {category}
- 위치: {area}
- 특징: {', '.join(tag_list)}

사용자 상황:
- 선호 음식: {', '.join(cuisine_filters) if cuisine_filters else '없음'}
- 날씨: {weather if weather else '없음'}
- 기분: {mood if mood else '없음'}
{emotion_context}

친근하고 자연스러운 말투로 이 메뉴를 추천하는 메시지를 작성해주세요.
- 추천 이유를 간단히 설명
- 이모지 적절히 사용
- 2-3문장으로 간결하게
- 마지막에 위치와 종류 정보 추가

형식:
[추천 멘트]

📍 위치: {area}
🍽️ 종류: {category}

응답:"""

        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini 응답 생성 실패: {e}, 기본 응답으로 fallback")
        return generate_response_message(choice, intent_data)


def generate_response_message(choice: dict, intent_data: Dict) -> str:
    """
    기본 응답 메시지를 생성합니다 (Fallback).
    """
    name = choice['name']
    category = choice.get('category', '')
    area = choice.get('area', '')
    
    cuisine_filters = intent_data.get('cuisine_filters', [])
    weather = intent_data.get('weather')
    mood = intent_data.get('mood')
    emotion = intent_data.get('emotion', 'neutral')
    
    # 상황별 멘트
    prefix = ""
    if emotion == "negative":
        prefix = "힘든 하루시네요 😔 든든하고 맛있는 걸로 기운 내세요! "
    elif cuisine_filters:
        prefix = f"{', '.join(cuisine_filters)} 좋아하시는군요! "
    elif weather == "비":
        prefix = "비 오는 날엔 이게 최고죠! 🌧️ "
    elif weather == "눈":
        prefix = "눈 오는 날엔 따뜻한 게 최고! ❄️ "
    elif weather == "더위":
        prefix = "더울 땐 시원한 게 최고! ☀️ "
    elif weather == "추위":
        prefix = "추울 땐 따뜻한 게 최고! 🥶 "
    elif mood == "피곤":
        prefix = "피곤할 땐 든든하게! 💪 "
    elif mood == "행복":
        prefix = "기분 좋은 날엔 맛있는 걸로! 😊 "
    elif mood == "우울":
        prefix = "기분 전환이 필요하시군요! 🌈 "
    elif mood == "화남":
        prefix = "맛있는 거 먹고 풀어요! 😤 "
    
    return f"{prefix}추천드립니다: [{name}] 🍜\n\n📍 위치: {area}\n🍽️ 종류: {category}"


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
    easter_egg_keywords = ["김형석", "만든사람", "만든 사람", "누가만듬", "개발자", "제작자"]
    
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
                "맑음": "맑은 날씨",
                "clear": "맑은 날씨",
                "cloudy": "흐린 날씨",
                "구름": "흐린 날씨"
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
                    if temp_value < 10:
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
    
    # 4. 의도 분석
    if GEMINI_AVAILABLE:
        intent_data = analyze_intent_with_gemini(utterance, conversation_history)
    else:
        intent_data = analyze_intent_fallback(utterance)
    
    intent = intent_data.get("intent", "recommend")
    casual_type = intent_data.get("casual_type")
    
    print(f"User: {user_id} | Intent: {intent} | Utterance: '{utterance}'")
    
    # 5. 의도별 처리
    response_text = ""
    
    if intent == "casual":
        # 일상 대화
        if GEMINI_AVAILABLE:
            casual_response = generate_casual_response_with_gemini(utterance, casual_type, conversation_history)
        else:
            casual_response = generate_casual_response_fallback(casual_type)
        
        # 점심 관련 키워드가 있거나, 짧은 입력(".") 일 때만 자동 추천
        should_recommend = (
            any(word in utterance.lower() for word in ["점심", "추천", "메뉴", "먹", "배고", "식사"]) or
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
                if GEMINI_AVAILABLE:
                    menu_response = generate_response_with_gemini(utterance, choice, intent_data, conversation_history)
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
            
            if GEMINI_AVAILABLE:
                response_text = generate_explanation_with_gemini(utterance, last_rec, conversation_history, weather, mood)
            else:
                response_text = f"{last_rec['name']}을(를) 추천한 이유는 맛있고 인기 있는 메뉴이기 때문이에요! 😊"
        else:
            response_text = "아직 추천드린 메뉴가 없어요. 점심 추천해드릴까요? 😊"
        session_manager.add_conversation(user_id, "user", utterance)
        session_manager.add_conversation(user_id, "bot", response_text)
    
    elif intent == "reject":
        # 추천 거부 - 다른 메뉴 추천
        last_rec = session_manager.get_last_recommendation(user_id)
        exclude_name = last_rec['name'] if last_rec else None
        
        params = payload.action.params
        weather = params.get("weather") or intent_data.get("weather")
        mood = params.get("mood") or intent_data.get("mood")
        cuisine_filters = intent_data.get("cuisine_filters") or None
        
        r = recommender.LunchRecommender()
        choice = r.recommend(weather=weather, cuisine_filters=cuisine_filters, mood=mood)
        
        # 이전 추천과 같으면 다시 시도
        if choice and exclude_name and choice['name'] == exclude_name:
            choice = r.recommend(weather=weather, cuisine_filters=cuisine_filters, mood=mood)
        
        if choice:
            session_manager.set_last_recommendation(user_id, choice)
            if GEMINI_AVAILABLE:
                response_text = f"알겠습니다! 그럼 다른 메뉴로 추천드릴게요 😊\n\n" + generate_response_with_gemini(utterance, choice, intent_data, conversation_history)
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
        choice = r.recommend(weather=weather, cuisine_filters=cuisine_filters, mood=mood)
        
        if choice:
            session_manager.set_last_recommendation(user_id, choice)
            if GEMINI_AVAILABLE:
                response_text = generate_response_with_gemini(utterance, choice, intent_data, conversation_history)
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
    
    return response

if __name__ == "__main__":
    uvicorn.run("bot_server:app", host="0.0.0.0", port=8000, reload=True)
