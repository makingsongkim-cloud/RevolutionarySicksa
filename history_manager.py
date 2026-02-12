import csv
import os
from datetime import datetime, timedelta
from collections import Counter

HISTORY_FILE = "lunch_history.csv"
# Persistent Storage Logic
DATA_DIR = os.path.join(os.path.expanduser("~"), ".lunch_siksa")
if not os.path.exists(DATA_DIR):
    try:
        os.makedirs(DATA_DIR)
    except:
        pass

if os.path.exists(DATA_DIR):
    HISTORY_FILE = os.path.join(DATA_DIR, "lunch_history.csv")

class LunchHistory:
    def __init__(self, filepath=HISTORY_FILE):
        self.filepath = filepath
        self.ensure_file_exists()

    def ensure_file_exists(self):
        """파일이 없으면 헤더와 함께 생성"""
        if not os.path.exists(self.filepath):
            with open(self.filepath, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["date", "menu_name", "area", "category", "episode", "user"])

    def load_history(self):
        """전체 기록을 리스트로 반환"""
        history = []
        if os.path.exists(self.filepath):
            with open(self.filepath, mode='r', newline='', encoding='utf-8') as f:
                # Check header for migration
                lines = f.readlines()
                if not lines: return []
                
                header = lines[0].strip().split(',')
                if "user" not in header or "episode" not in header: # Old format migration on read
                     # Simple strategy: treat all old records as "Master"
                     pass 

                # Reset to read as Dict
                f.seek(0)
                reader = csv.DictReader(f)
                for row in reader:
                    if 'user' not in row: row['user'] = "Master" # Default for old data
                    if 'episode' not in row: row['episode'] = ""
                    history.append(row)
        return history

    def save_record(self, menu_name, area, category, user="Master", record_date=None, episode=None):
        """오늘 날짜로 메뉴 기록 저장"""
        today = datetime.now().strftime("%Y-%m-%d")
        target_date = record_date if record_date else today
        episode_value = episode if episode else ""
        
        # Check if header needs update (migration)
        self._check_and_migrate_header()
            
        with open(self.filepath, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([target_date, menu_name, area, category, episode_value, user])

    def _check_and_migrate_header(self):
        """헤더에 user 컬럼 없으면 추가 (Migration)"""
        if not os.path.exists(self.filepath): return
        
        with open(self.filepath, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
        
        if "user" not in first_line or "episode" not in first_line:
             # Read all, add user column, rewrite
             with open(self.filepath, 'r', encoding='utf-8') as f:
                 reader = csv.DictReader(f)
                 rows = list(reader)
             
             with open(self.filepath, 'w', newline='', encoding='utf-8') as f:
                 writer = csv.writer(f)
                 writer.writerow(["date", "menu_name", "area", "category", "episode", "user"])
                 for r in rows:
                     writer.writerow([
                         r.get('date', ''),
                         r.get('menu_name', ''),
                         r.get('area', ''),
                         r.get('category', ''),
                         r.get('episode', ''),
                         r.get('user', 'Master')
                     ])
    
    def get_recent_menus(self, days=2, user="Master"):
        """최근 N일간 먹은 메뉴 이름 세트 반환 (사용자별)"""
        history = self.load_history()
        recent_menus = set()
        
        today = datetime.now().date()
        cutoff_date = today - timedelta(days=days)

        for row in history:
            if row.get('user') != user: continue # Filter by user
            
            try:
                row_date = datetime.strptime(row['date'], "%Y-%m-%d").date()
                if row_date >= cutoff_date and row_date < today:
                     recent_menus.add(row['menu_name'])
                elif row_date == today:
                     recent_menus.add(row['menu_name'])     
            except ValueError:
                continue
                
        return recent_menus

    def get_stats(self, days=None, user="Master"):
        """통계 데이터 반환 (사용자별)"""
        history = self.load_history()
        
        target_history = []
        
        # 1. Filter by User
        user_history = [h for h in history if h.get('user') == user]
        
        if days is None:
            target_history = user_history
        else:
            today = datetime.now().date()
            cutoff_date = today - timedelta(days=days)
            for row in user_history:
                try:
                    row_date = datetime.strptime(row['date'], "%Y-%m-%d").date()
                    if row_date >= cutoff_date:
                        target_history.append(row)
                except ValueError:
                    continue

        area_counts = Counter(row['area'] for row in target_history)
        category_counts = Counter(row['category'] for row in target_history)
        return area_counts, category_counts

    def get_records(self, days=None, user="Master"):
        """필터링된 원본 기록 반환 (사용자별)"""
        history = self.load_history()
        
        # 1. Filter by User
        user_history = [h for h in history if h.get('user') == user]
        
        target_history = []
        if days is None:
            target_history = user_history
        else:
            today = datetime.now().date()
            cutoff_date = today - timedelta(days=days)
            for row in user_history:
                try:
                    row_date = datetime.strptime(row['date'], "%Y-%m-%d").date()
                    if row_date >= cutoff_date:
                        target_history.append(row)
                except ValueError:
                    continue
        
        return list(reversed(target_history))

    def delete_todays_record(self, user="Master"):
        """오늘 날짜로 저장된 사용자의 마지막 기록을 삭제함"""
        if not os.path.exists(self.filepath):
            return False

        with open(self.filepath, mode='r', encoding='utf-8', newline='') as f:
            reader = list(csv.reader(f))

        if len(reader) <= 1:
            return False

        header = reader[0]
        try:
            date_idx = header.index("date")
            user_idx = header.index("user")
        except ValueError:
            return False

        today_str = datetime.now().strftime("%Y-%m-%d")
        target_index = -1

        for i in range(len(reader) - 1, 0, -1):
            row = reader[i]
            if not row or len(row) <= max(date_idx, user_idx):
                continue
            r_date = row[date_idx]
            r_user = row[user_idx]
            if r_date == today_str and r_user == user:
                target_index = i
                break

        if target_index != -1:
            del reader[target_index]
            with open(self.filepath, mode='w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(reader)
            return True
            
        return False

    def clear_all_history(self):
        """기록 전체 초기화 (헤더만 남김)"""
        try:
            with open(self.filepath, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["date", "menu_name", "area", "category", "episode", "user"])
            return True
        except:
            return False

    def export_history(self, target_path):
        """기록 파일 백업 (복사)"""
        import shutil
        try:
            if os.path.exists(self.filepath):
                shutil.copy2(self.filepath, target_path)
                return True
        except:
            pass
        return False

    def get_history_logs(self, days=None, user="Master"):
        """Streamlit 로그용 문자열 리스트 반환 (사용자별)"""
        records = self.get_records(days=days, user=user)
        logs = []
        for r in records:
            episode = r.get('episode')
            ep_part = f" | {episode}회" if episode else ""
            log_str = f"{r.get('date')}{ep_part} | {r.get('menu_name')} ({r.get('category')}) - {r.get('area')}"
            logs.append(log_str)
        return logs
