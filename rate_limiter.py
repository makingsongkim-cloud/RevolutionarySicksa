"""
Rate Limiter 모듈
악성 사용자로부터 API 비용을 보호합니다.
"""
from datetime import datetime, timedelta
from typing import Dict, Tuple
import threading

class RateLimiter:
    def __init__(
        self,
        max_requests_per_minute: int = 10,
        max_requests_per_hour: int = 50,
        max_requests_per_day: int = 200
    ):
        self.max_per_minute = max_requests_per_minute
        self.max_per_hour = max_requests_per_hour
        self.max_per_day = max_requests_per_day
        
        # 사용자별 요청 기록
        self.user_requests: Dict[str, list] = {}
        self.lock = threading.Lock()
    
    def is_allowed(self, user_id: str) -> Tuple[bool, str]:
        """
        사용자의 요청이 허용되는지 확인합니다.
        
        Returns:
            (허용 여부, 거부 사유)
        """
        with self.lock:
            now = datetime.now()
            
            # 사용자 요청 기록 가져오기
            if user_id not in self.user_requests:
                self.user_requests[user_id] = []
            
            requests = self.user_requests[user_id]
            
            # 오래된 기록 정리
            requests = [req_time for req_time in requests if now - req_time < timedelta(days=1)]
            self.user_requests[user_id] = requests
            
            # 분당 제한 체크
            minute_ago = now - timedelta(minutes=1)
            requests_last_minute = sum(1 for req_time in requests if req_time > minute_ago)
            if requests_last_minute >= self.max_per_minute:
                return False, f"분당 최대 {self.max_per_minute}회 요청 제한을 초과했습니다. 잠시 후 다시 시도해주세요."
            
            # 시간당 제한 체크
            hour_ago = now - timedelta(hours=1)
            requests_last_hour = sum(1 for req_time in requests if req_time > hour_ago)
            if requests_last_hour >= self.max_per_hour:
                return False, f"시간당 최대 {self.max_per_hour}회 요청 제한을 초과했습니다. 나중에 다시 시도해주세요."
            
            # 일일 제한 체크
            day_ago = now - timedelta(days=1)
            requests_last_day = sum(1 for req_time in requests if req_time > day_ago)
            if requests_last_day >= self.max_per_day:
                return False, f"일일 최대 {self.max_per_day}회 요청 제한을 초과했습니다. 내일 다시 이용해주세요."
            
            # 요청 기록 추가
            self.user_requests[user_id].append(now)
            
            return True, ""
    
    def get_usage_stats(self, user_id: str) -> Dict[str, int]:
        """
        사용자의 사용량 통계를 반환합니다.
        """
        with self.lock:
            if user_id not in self.user_requests:
                return {
                    "last_minute": 0,
                    "last_hour": 0,
                    "last_day": 0
                }
            
            now = datetime.now()
            requests = self.user_requests[user_id]
            
            minute_ago = now - timedelta(minutes=1)
            hour_ago = now - timedelta(hours=1)
            day_ago = now - timedelta(days=1)
            
            return {
                "last_minute": sum(1 for req_time in requests if req_time > minute_ago),
                "last_hour": sum(1 for req_time in requests if req_time > hour_ago),
                "last_day": sum(1 for req_time in requests if req_time > day_ago)
            }
    
    def reset_user(self, user_id: str):
        """
        특정 사용자의 사용량을 초기화합니다. (관리자 기능)
        """
        with self.lock:
            if user_id in self.user_requests:
                del self.user_requests[user_id]

# 전역 Rate Limiter 인스턴스
rate_limiter = RateLimiter(
    max_requests_per_minute=10,   # 분당 10회
    max_requests_per_hour=50,      # 시간당 50회
    max_requests_per_day=200       # 일일 200회
)
