"""
세션 관리 모듈
사용자별 대화 컨텍스트를 메모리에 저장하고 관리합니다.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import threading

class SessionManager:
    def __init__(self, session_timeout_minutes: int = 30):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.lock = threading.Lock()
    
    def get_session(self, user_id: str) -> Dict[str, Any]:
        """
        사용자 세션을 가져옵니다. 없으면 새로 생성합니다.
        """
        with self.lock:
            # 세션 만료 체크
            self._cleanup_expired_sessions()
            
            if user_id not in self.sessions:
                self.sessions[user_id] = self._create_new_session(user_id)
            
            # 마지막 접근 시간 업데이트
            self.sessions[user_id]["last_updated"] = datetime.now()
            return self.sessions[user_id]
    
    def update_session(self, user_id: str, data: Dict[str, Any]):
        """
        세션 데이터를 업데이트합니다.
        """
        with self.lock:
            if user_id in self.sessions:
                self.sessions[user_id].update(data)
                self.sessions[user_id]["last_updated"] = datetime.now()
    
    def add_conversation(self, user_id: str, role: str, message: str, recommendation: Optional[Dict] = None):
        """
        대화 히스토리에 메시지를 추가합니다.
        """
        session = self.get_session(user_id)
        
        conversation_entry = {
            "role": role,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if recommendation:
            conversation_entry["recommendation"] = recommendation
        
        session["conversation_history"].append(conversation_entry)
        
        # 최근 10개만 유지
        if len(session["conversation_history"]) > 10:
            session["conversation_history"] = session["conversation_history"][-10:]
    
    def set_last_recommendation(self, user_id: str, recommendation: Dict[str, Any]):
        """
        마지막 추천 정보를 저장하고 카운트를 증가시킵니다.
        """
        session = self.get_session(user_id)
        session["last_recommendation"] = recommendation
        session["recommendation_count"] = session.get("recommendation_count", 0) + 1
    
    def get_last_recommendation(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        마지막 추천 정보를 가져옵니다.
        """
        session = self.get_session(user_id)
        return session.get("last_recommendation")
    
    def get_conversation_history(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        대화 히스토리를 가져옵니다.
        """
        session = self.get_session(user_id)
        history = session["conversation_history"]
        return history[-limit:] if len(history) > limit else history
    
    def clear_session(self, user_id: str):
        """
        특정 사용자의 세션을 삭제합니다.
        """
        with self.lock:
            if user_id in self.sessions:
                del self.sessions[user_id]
    
    def _create_new_session(self, user_id: str) -> Dict[str, Any]:
        """
        새로운 세션을 생성합니다.
        """
        return {
            "user_id": user_id,
            "created_at": datetime.now(),
            "last_updated": datetime.now(),
            "conversation_history": [],
            "last_recommendation": None,
            "recommendation_count": 0,
            "preferences": {}
        }
    
    def _cleanup_expired_sessions(self):
        """
        만료된 세션을 정리합니다.
        """
        now = datetime.now()
        expired_users = [
            user_id for user_id, session in self.sessions.items()
            if now - session["last_updated"] > self.session_timeout
        ]
        
        for user_id in expired_users:
            del self.sessions[user_id]
            print(f"세션 만료: {user_id}")

# 전역 세션 매니저 인스턴스
session_manager = SessionManager()
