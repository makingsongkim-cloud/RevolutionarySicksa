import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import recommender
import lunch_data
from history_manager import LunchHistory

# Basic config (모던 클린 디자인)
ctk.set_appearance_mode("System") # 시스템 설정 따름 (보통 라이트)
ctk.set_default_color_theme("blue")

# Palette (Modern Clean)
# Palette (Tone Down)
COLOR_BG = "#E0E0E0"        # Toned down Gray
COLOR_FRAME = "#F5F5F5"     # Off-White Cards
COLOR_TEXT_MAIN = "#1F2937" # Dark Slate
COLOR_TEXT_DIM = "#6B7280"  # Muted Gray
COLOR_ACCENT = "#3B82F6"    # Primary Blue
COLOR_HIGHLIGHT = "#10B981" # Green
COLOR_BORDER = "#D1D5DB"    # Darker Border for contrast
COLOR_DANGER = "#EF4444"    # Red
# Lazy load Matplotlib to speed up startup
MATPLOTLIB_AVAILABLE = True # Assume true, check later or handle import error inside function

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Revolutionary Sicksa")
        self.geometry("600x650")
        self.configure(fg_color=COLOR_BG)

        self.recommender = recommender.LunchRecommender()
        self.history = LunchHistory()
        self.current_recommendation = None
        self.weather_condition = "로딩중..."

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 2, 3), weight=0)

        self.create_widgets()
        
        # Start weather fetch in background
        self.start_weather_fetch()

    def bring_window_front(self, window):
        """Bring a Toplevel to front once, then release always-on-top to avoid hiding other dialogs."""
        window.lift()
        try:
            window.attributes("-topmost", True)
            window.after(200, lambda: window.attributes("-topmost", False))
        except Exception:
            pass

    def create_widgets(self):
        # 1. Header Frame
        self.header_frame = ctk.CTkFrame(self, corner_radius=20, fg_color=COLOR_FRAME) # Rounded
        self.header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        
        self.lbl_title = ctk.CTkLabel(
            self.header_frame,
            text="지존 마스터님 식사하시죠", 
            font=ctk.CTkFont(family="AppleGothic", size=26, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        self.lbl_title.pack(pady=(20, 5))

        self.lbl_weather = ctk.CTkLabel(
            self.header_frame,
            text="날씨 확인 중...",
            text_color=COLOR_TEXT_DIM,
            font=ctk.CTkFont(family="AppleGothic", size=14)
        )
        self.lbl_weather.pack(pady=(0, 20))

        # 2. Filter Frame
        self.filter_frame = ctk.CTkFrame(self, fg_color=COLOR_FRAME, corner_radius=20)
        self.filter_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        ctk.CTkLabel(
            self.filter_frame,
            text="메뉴 취향 선택",
            font=ctk.CTkFont(family="AppleGothic", size=16, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        ).pack(pady=15)

        # Checkboxes for cuisines
        self.cuisine_vars = {}
        cuisines = [
            lunch_data.CUISINE_KOREAN, lunch_data.CUISINE_CHINESE, 
            lunch_data.CUISINE_JAPANESE, lunch_data.CUISINE_WESTERN, 
            lunch_data.CUISINE_SNACK
        ]
        
        # Grid layout for checkboxes
        cb_subframe = ctk.CTkFrame(self.filter_frame, fg_color="transparent")
        cb_subframe.pack(pady=5)
        
        for idx, cuisine in enumerate(cuisines):
            var = ctk.StringVar(value="") 
            cb = ctk.CTkCheckBox(
                cb_subframe,
                text=cuisine,
                variable=var,
                onvalue=cuisine,
                offvalue="",
                fg_color=COLOR_ACCENT,
                hover_color=COLOR_ACCENT,
                text_color=COLOR_TEXT_MAIN,
                font=ctk.CTkFont(family="AppleGothic", size=13)
            )
            cb.grid(row=0, column=idx, padx=8, pady=10)
            self.cuisine_vars[cuisine] = var
            
        # Mood Selection
        mood_frame = ctk.CTkFrame(self.filter_frame, fg_color="transparent")
        mood_frame.pack(pady=(5, 20))
        
        ctk.CTkLabel(
            mood_frame,
            text="오늘 기분은?",
            font=ctk.CTkFont(family="AppleGothic", size=14, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        ).pack(side="left", padx=10)
        
        self.mood_var = ctk.StringVar(value="보통")
        mood_cb = ctk.CTkComboBox(
            mood_frame,
            values=["보통", "화남", "행복", "우울", "피곤"],
            variable=self.mood_var,
            fg_color=COLOR_FRAME,   # Match card bg
            border_color=COLOR_BORDER,
            button_color=COLOR_ACCENT,
            dropdown_fg_color=COLOR_FRAME,
            text_color=COLOR_TEXT_MAIN,
            font=ctk.CTkFont(family="AppleGothic", size=13),
            corner_radius=10
        )
        mood_cb.pack(side="left", padx=5)
        
        # 3. Action Area
        self.btn_recommend = ctk.CTkButton(
            self,
            text="메뉴 추천받기",
            command=self.do_recommend,
            height=50,
            font=ctk.CTkFont(family="AppleGothic", size=18, weight="bold"),
            fg_color=COLOR_ACCENT,
            hover_color="#2563EB", # Darker Blue
            text_color="white",
            corner_radius=25
        )
        self.btn_recommend.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        # 4. Result Area
        self.result_frame = ctk.CTkFrame(self, fg_color=COLOR_FRAME, corner_radius=20)
        self.result_frame.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        
        self.lbl_result_name = ctk.CTkLabel(
            self.result_frame,
            text="버튼을 눌러보세요",
            font=ctk.CTkFont(family="AppleGothic", size=24, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        self.lbl_result_name.pack(pady=(25, 5))
        
        self.lbl_result_detail = ctk.CTkLabel(
            self.result_frame,
            text="",
            font=ctk.CTkFont(family="AppleGothic", size=14),
            text_color=COLOR_TEXT_DIM
        )
        self.lbl_result_detail.pack(pady=5)

        # Accept Button (Hidden initially)
        self.btn_accept = ctk.CTkButton(
            self.result_frame,
            text="이걸로 결정!",
            command=self.accept_recommendation,
            fg_color=COLOR_HIGHLIGHT,
            hover_color="#059669",
            text_color="white",
            font=ctk.CTkFont(family="AppleGothic", size=14, weight="bold"),
            corner_radius=15
        )
        # will pack when needed

        # 5. Stats & Manage Buttons (Bottom)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, pady=10)
        
        self.btn_stats = ctk.CTkButton(
            btn_frame,
            text="통계/로그",
            command=self.show_stats,
            fg_color="transparent",
            border_width=0,
            hover_color=COLOR_FRAME,
            text_color=COLOR_TEXT_DIM,
            font=ctk.CTkFont(family="AppleGothic", size=12, underline=True)
        )
        self.btn_stats.pack(side="left", padx=10)

        self.btn_manage = ctk.CTkButton(
            btn_frame,
            text="데이터 관리",
            command=self.show_manage,
            fg_color="transparent",
            border_width=0,
            hover_color=COLOR_FRAME,
            text_color=COLOR_TEXT_DIM,
            font=ctk.CTkFont(family="AppleGothic", size=12, underline=True)
        )
        self.btn_manage.pack(side="left", padx=10)

        self.btn_help = ctk.CTkButton(
            btn_frame,
            text="도움말",
            command=self.show_help,
            width=50,
            fg_color="transparent",
            border_width=1,
            border_color=COLOR_TEXT_DIM,
            hover_color=COLOR_FRAME,
            text_color=COLOR_TEXT_DIM,
            font=ctk.CTkFont(family="AppleGothic", size=12),
            corner_radius=10
        )
        self.btn_help.pack(side="left", padx=10)

        # Native Menu Bar
        self.create_menu_bar()

    def create_menu_bar(self):
        menubar = tk.Menu(self)
        
        # Settings Menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="날씨 위치 변경", command=self.change_location)
        settings_menu.add_command(label="데이터 관리", command=self.show_manage)
        settings_menu.add_command(label="기록/통계 보기", command=self.show_stats)
        menubar.add_cascade(label="설정", menu=settings_menu)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="도움말 보기", command=self.show_help)
        menubar.add_cascade(label="도움말", menu=help_menu)
        
        self.config(menu=menubar)

    def change_location(self):
        """위치 자동 감지 다이얼로그 (IP 기반)"""
        top = ctk.CTkToplevel(self)
        top.title("위치 설정")
        top.geometry("320x220")
        top.configure(fg_color=COLOR_BG)
        self.bring_window_front(top)

        ctk.CTkLabel(
            top,
            text="현재 위치를 스캔하여 날씨를 가져옵니다.\n아래 버튼을 눌러주세요.",
            justify="center",
            text_color=COLOR_TEXT_MAIN,
            font=ctk.CTkFont(family="AppleGothic", size=13)
        ).pack(pady=15)

        status_var = tk.StringVar(value="대기 중")
        ctk.CTkLabel(top, textvariable=status_var, text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(family="AppleGothic", size=12)).pack(pady=(0, 10))

        def do_autodetect():
            status_var.set("스캔 중...")

            def worker():
                city = self.recommender.detect_city_by_ip()
                target_city = city or "Seoul"
                lunch_data.save_config({"location": target_city})
                cond, temp = self.recommender.get_weather(location=target_city)
                if cond is None:
                    cond, temp = "맑음", ""
                self.weather_condition = cond

                def update_ui():
                    status_var.set(f"완료: {target_city}")
                    self.lbl_weather.configure(text=f"{cond} {temp}")
                self.after(0, update_ui)

            threading.Thread(target=worker, daemon=True).start()

        ctk.CTkButton(
            top,
            text="위치 스캔 시작",
            command=do_autodetect,
            fg_color=COLOR_ACCENT,
            hover_color="#2563EB",
            text_color="white",
            font=ctk.CTkFont(family="AppleGothic", size=14, weight="bold"),
            corner_radius=20
        ).pack(pady=10)

        ctk.CTkLabel(
            top,
            text="(IP 기반이므로 VPN 사용 시 오차가 있을 수 있습니다)",
            text_color=COLOR_TEXT_DIM,
            font=ctk.CTkFont(size=11)
        ).pack(pady=5)


    def start_weather_fetch(self):
        def fetch():
            self.lbl_weather.configure(text="위치 확인 중...")
            
            # 1. Detect Location (Auto) or Load Config
            # Prioritize Config if exists, else Auto-detect
            cfg = lunch_data.load_config()
            saved_loc = cfg.get("location")
            
            target_city = "Sangam-dong" # Default fallback per user context
            
            if saved_loc:
                target_city = saved_loc
            else:
                detected = self.recommender.detect_city_by_ip()
                if detected:
                    target_city = detected
            
            # 2. Fetch Weather
            cond, temp = self.recommender.get_weather(location=target_city)
            
            # Retry with Sangam if failed
            if cond is None:
                target_city = "Sangam-dong"
                cond, temp = self.recommender.get_weather(location="Sangam-dong")
            
            # Display Name Mapping (Localization)
            # Remove country code if present (e.g., "Seoul,KR" -> "Seoul")
            if "," in target_city:
                clean_city = target_city.split(",")[0].strip()
            else:
                clean_city = target_city.strip()
            
            display_city = clean_city # Default to clean string
            
            city_map = {
                "Seoul": "서울",
                "Gangnam-gu": "강남구",
                "Gangnam-Gu": "강남구",
                "Sangam-dong": "상암동",
                "Mapo-gu": "마포구",
                "Seongnam-si": "성남시",
                "Bundang-gu": "분당구",
                "Seongnam": "성남",
                "Incheon": "인천",
                "Busan": "부산"
            }
            
            # 1. Exact Match
            if clean_city in city_map:
                display_city = city_map[clean_city]
            else:
                # 2. Partial Match (for safety)
                if "Gangnam" in clean_city: display_city = "강남구"
                elif "Sangam" in clean_city: display_city = "상암동"
                elif "Seoul" in clean_city: display_city = "서울"

            if cond is None:
                cond, temp = "정보 없음", "" 
                display_city = display_city or "상암동"
                self.weather_condition = "정보 없음"
            else:
                self.weather_condition = cond

            if not temp:
                temp = ""

            display_text = f"{display_city}  |  {cond} {temp}".strip()
            
            # Update UI on main thread
            self.after(0, lambda: self.lbl_weather.configure(text=display_text))
        
        threading.Thread(target=fetch, daemon=True).start()

    def do_recommend(self):
        # Refresh menus first (in case added)
        lunch_data.refresh_menus()
        self.recommender.refresh_data()

        # Collect filters
        selected_cuisines = []
        for c, var in self.cuisine_vars.items():
            val = var.get()
            if val:
                selected_cuisines.append(val)
        
        filters = selected_cuisines if selected_cuisines else None
        mood = self.mood_var.get()

        rec = self.recommender.recommend(weather=self.weather_condition, cuisine_filters=filters, mood=mood)
        
        if rec:
            self.current_recommendation = rec
            self.lbl_result_name.configure(text=rec['name'])
            self.lbl_result_detail.configure(text=f"[{rec['cuisine']}] {rec['category']} | {rec['area']}")
            self.btn_accept.pack(pady=20)
        else:
            self.lbl_result_name.configure(text="추천 데이터 없음 🚫")
            self.lbl_result_detail.configure(text="조건을 변경하거나 데이터를 추가하세요.")
            self.btn_accept.pack_forget()

    def accept_recommendation(self):
        if not self.current_recommendation:
            return
        
        rec = self.current_recommendation
        self.history.save_record(rec['name'], rec['area'], rec['category'])
        
        messagebox.showinfo("시스템 알림", f"선택 완료! '{rec['name']}' 저장됨.")
        
        self.btn_accept.pack_forget()
        self.lbl_result_name.configure(text="맛있게 드세요!")
        self.lbl_result_detail.configure(text="")

    def show_manage(self):
        top = ctk.CTkToplevel(self)
        top.title("데이터 관리")
        top.geometry("600x720") # Adjusted height
        top.configure(fg_color=COLOR_BG) # Fix background
        self.bring_window_front(top)
        
        # Make resizable
        top.grid_columnconfigure(0, weight=1)
        top.grid_rowconfigure(0, weight=1)

        # Consistent Tabview
        tab_view = ctk.CTkTabview(
            top, 
            fg_color=COLOR_BG, 
            text_color=COLOR_TEXT_MAIN,
            segmented_button_fg_color=COLOR_BORDER,
            segmented_button_selected_color=COLOR_ACCENT,
            segmented_button_selected_hover_color="#2563EB",
            segmented_button_unselected_color=COLOR_FRAME,
            segmented_button_unselected_hover_color="#F3F4F6"
        )
        tab_view.pack(fill="both", expand=True, padx=20, pady=20)
        
        tab_add = tab_view.add("가게 추가")
        tab_list = tab_view.add("가게 목록/관리")
        tab_data = tab_view.add("백업 및 초기화")

        # --- Tab 1: Add Menu (Compact) ---
        ctk.CTkLabel(tab_add, text="새로운 맛집 등록", font=("", 16, "bold")).pack(pady=10)
        
        # Revert to standard Frame (no scrollbar)
        input_frame = ctk.CTkFrame(tab_add, fg_color="transparent")
        input_frame.pack(fill="both", expand=True, padx=10)

        # Name
        ctk.CTkLabel(input_frame, text="가게/메뉴 이름 *").pack(anchor="w", pady=(5, 2))
        entry_name = ctk.CTkEntry(input_frame)
        entry_name.pack(fill="x", pady=(0, 5))

        # Area
        ctk.CTkLabel(input_frame, text="위치 (구역) *").pack(anchor="w", pady=(5, 2))
        entry_area = ctk.CTkComboBox(input_frame, values=[lunch_data.AREA_BASEMENT, lunch_data.AREA_YTN, lunch_data.AREA_MEOKJA, "기타"])
        entry_area.pack(fill="x", pady=(0, 5))
        
        # Category
        ctk.CTkLabel(input_frame, text="상세 메뉴명 (예: 김치찌개, 돈까스) *").pack(anchor="w", pady=(5, 2))
        entry_cat = ctk.CTkEntry(input_frame)
        entry_cat.pack(fill="x", pady=(0, 5))
        
        # Cuisine
        ctk.CTkLabel(input_frame, text="음식 종류 *").pack(anchor="w", pady=(5, 2))
        entry_cuisine = ctk.CTkComboBox(input_frame, values=[
            lunch_data.CUISINE_KOREAN, lunch_data.CUISINE_CHINESE, lunch_data.CUISINE_JAPANESE,
            lunch_data.CUISINE_WESTERN, lunch_data.CUISINE_SNACK, lunch_data.CUISINE_OTHER
        ])
        entry_cuisine.pack(fill="x", pady=(0, 5))

        # Tags (Checkboxes)
        ctk.CTkLabel(input_frame, text="특징 (다중 선택)").pack(anchor="w", pady=(5, 2))
        tag_frame = ctk.CTkFrame(input_frame)
        tag_frame.pack(fill="x", pady=2)
        
        tags_vars = {}
        tag_list = [lunch_data.TAG_RICE, lunch_data.TAG_NOODLE, lunch_data.TAG_SOUP, lunch_data.TAG_MEAT, 
                    lunch_data.TAG_SPICY, lunch_data.TAG_HOT, lunch_data.TAG_HEAVY, lunch_data.TAG_LIGHT]
        
        for idx, t in enumerate(tag_list):
            v = ctk.StringVar(value="")
            cb = ctk.CTkCheckBox(tag_frame, text=t, variable=v, onvalue=t, offvalue="")
            cb.grid(row=idx//2, column=idx%2, sticky="w", padx=5, pady=2)
            tags_vars[t] = v

        def save_menu():
            name = entry_name.get().strip()
            cat = entry_cat.get().strip()
            area = entry_area.get()
            cuisine = entry_cuisine.get()
            
            if not name or not cat:
                messagebox.showerror("오류", "이름과 메뉴명을 입력해주세요.")
                return
            
            # Collect tags
            selected_tags = [v.get() for v in tags_vars.values() if v.get()]
            
            success = lunch_data.save_new_menu(name, area, cat, cuisine, selected_tags)
            if success:
                messagebox.showinfo("성공", "메뉴가 추가되었습니다!\n바로 추천 목록에 반영됩니다.")
                entry_name.delete(0, "end")
                entry_cat.delete(0, "end")
                # Reload data in main app happens in do_recommend
            else:
                messagebox.showerror("실패", "저장에 실패했거나 이미 있는 이름입니다.")

        ctk.CTkButton(input_frame, text="저장하기", command=save_menu, fg_color="#2CC985", hover_color="#229965").pack(pady=15)


        # --- Tab 2: Shop List & Delete & Edit ---
        # Scrollable Frame for list
        list_frame = ctk.CTkScrollableFrame(tab_list, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        def refresh_list():
            # Clear
            for widget in list_frame.winfo_children():
                widget.destroy()
            
            # Load current menus
            current_menus = lunch_data.load_menus()
            
            if not current_menus:
                 ctk.CTkLabel(list_frame, text="등록된 가게가 없습니다.").pack(pady=20)
                 return
                 
            for m in current_menus:
                row = ctk.CTkFrame(list_frame, fg_color=COLOR_FRAME, border_width=1, border_color=COLOR_BORDER)
                row.pack(fill="x", pady=2)
                
                info_text = f"[{m['cuisine']}] {m['name']} ({m['category']}) - {m['area']}"
                ctk.CTkLabel(row, text=info_text, anchor="w", text_color=COLOR_TEXT_MAIN, font=ctk.CTkFont(family="AppleGothic", size=12)).pack(side="left", padx=10, pady=5, fill="x", expand=True)
                
                # Delete Button
                def delete_handler(name=m['name']):
                    if messagebox.askyesno("삭제 확인", f"정말 '{name}'을(를) 삭제하시겠습니까?"):
                        if lunch_data.delete_menu(name):
                            messagebox.showinfo("삭제됨", "삭제되었습니다.")
                            refresh_list() # UI refresh
                        else:
                            messagebox.showerror("오류", "삭제 실패.")
                
                ctk.CTkButton(row, text="삭제", fg_color="transparent", border_width=0, hover_color="#FEE2E2", width=50, text_color=COLOR_DANGER,
                              command=delete_handler, font=ctk.CTkFont(family="AppleGothic", size=12)).pack(side="right", padx=5, pady=5)

                # Edit Button
                def edit_handler(target_menu=m):
                    edit_win = ctk.CTkToplevel(top)
                    edit_win.title(f"메뉴 수정: {target_menu['name']}")
                    edit_win.geometry("400x550")
                    self.bring_window_front(edit_win)

                    sc_frame = ctk.CTkScrollableFrame(edit_win)
                    sc_frame.pack(fill="both", expand=True, padx=10, pady=10)

                    # Fields
                    ctk.CTkLabel(sc_frame, text="가게/메뉴 이름").pack(anchor="w")
                    e_name = ctk.CTkEntry(sc_frame)
                    e_name.pack(fill="x")
                    e_name.insert(0, target_menu['name'])

                    ctk.CTkLabel(sc_frame, text="위치").pack(anchor="w")
                    e_area = ctk.CTkComboBox(sc_frame, values=[lunch_data.AREA_BASEMENT, lunch_data.AREA_YTN, lunch_data.AREA_MEOKJA, "기타"])
                    e_area.pack(fill="x")
                    e_area.set(target_menu['area'])

                    ctk.CTkLabel(sc_frame, text="상세 메뉴명").pack(anchor="w")
                    e_cat = ctk.CTkEntry(sc_frame)
                    e_cat.pack(fill="x")
                    e_cat.insert(0, target_menu['category'])

                    ctk.CTkLabel(sc_frame, text="음식 종류").pack(anchor="w")
                    e_cuisine = ctk.CTkComboBox(sc_frame, values=[
                        lunch_data.CUISINE_KOREAN, lunch_data.CUISINE_CHINESE, lunch_data.CUISINE_JAPANESE,
                        lunch_data.CUISINE_WESTERN, lunch_data.CUISINE_SNACK, lunch_data.CUISINE_OTHER
                    ])
                    e_cuisine.pack(fill="x")
                    e_cuisine.set(target_menu['cuisine'])

                    ctk.CTkLabel(sc_frame, text="특징").pack(anchor="w")
                    t_frame = ctk.CTkFrame(sc_frame)
                    t_frame.pack(fill="x")
                    
                    e_vars = {}
                    current_tags = target_menu.get("tags", [])
                    tag_list = [lunch_data.TAG_RICE, lunch_data.TAG_NOODLE, lunch_data.TAG_SOUP, lunch_data.TAG_MEAT, 
                                lunch_data.TAG_SPICY, lunch_data.TAG_HOT, lunch_data.TAG_HEAVY, lunch_data.TAG_LIGHT]

                    for idx, t in enumerate(tag_list):
                        v = ctk.StringVar(value=t if t in current_tags else "")
                        cb = ctk.CTkCheckBox(t_frame, text=t, variable=v, onvalue=t, offvalue="")
                        cb.grid(row=idx//2, column=idx%2, sticky="w", padx=5, pady=2)
                        e_vars[t] = v

                    def save_edit():
                        new_name = e_name.get().strip()
                        if not new_name: return
                        
                        updated_data = {
                            "name": new_name,
                            "area": e_area.get(),
                            "category": e_cat.get(),
                            "cuisine": e_cuisine.get(),
                            "tags": [v.get() for v in e_vars.values() if v.get()]
                        }
                        
                        success, message = lunch_data.update_menu(target_menu['name'], updated_data)
                        if success:
                            messagebox.showinfo("성공", message)
                            edit_win.destroy()
                            refresh_list()
                        else:
                            messagebox.showerror("실패", message)
                            # Bring window to front again
                            edit_win.lift()
                            edit_win.attributes("-topmost", True)

                    ctk.CTkButton(sc_frame, text="수정 저장", command=save_edit, fg_color="#229965").pack(pady=20)

                ctk.CTkButton(row, text="수정", width=60, command=edit_handler).pack(side="right", padx=5, pady=5)

        # Refresh button (or auto refresh when tab clicked? Tabview doesn't have easy event binding for tab switch in ctk yet without overriding)
        # Add a manual Refresh button at top
        ctk.CTkButton(tab_list, text="목록 새로고침", command=refresh_list, height=30).pack(fill="x", padx=10, pady=5)
        
        # Initial load
        refresh_list()


        # --- Tab 3: Backup & Reset ---
        ctk.CTkLabel(tab_data, text="데이터 안전 관리", font=("", 16, "bold")).pack(pady=20)
        
        def do_backup():
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
            if path:
                if self.history.export_history(path):
                    messagebox.showinfo("완료", "백업되었습니다.")
                else:
                    messagebox.showerror("오류", "백업 실패.")
        
        ctk.CTkButton(tab_data, text="CSV로 내보내기", command=do_backup, fg_color=COLOR_ACCENT, hover_color="#2563EB", text_color="white", font=ctk.CTkFont(family="AppleGothic", size=13), corner_radius=10).pack(pady=10)
        
        def do_reset():
            if messagebox.askyesno("경고", "정말로 모든 점심 기록을 초기화하시겠습니까?\n이 작업은 되돌릴 수 없습니다!"):
                if self.history.clear_all_history():
                    messagebox.showinfo("완료", "모든 기록이 삭제되었습니다.")
                else:
                    messagebox.showerror("실패", "초기화 실패.")
                    
        ctk.CTkButton(tab_data, text="기록 전체 초기화", fg_color="#D14D4D", hover_color="#962D2D", command=do_reset).pack(pady=30)


    def show_stats(self):
        # Lazy Import Matplotlib
        global MATPLOTLIB_AVAILABLE
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            import platform
            
            # Font Config (Only on first load)
            system_name = platform.system()
            if system_name == "Darwin": # macOS
                plt.rc('font', family='AppleGothic') 
            elif system_name == "Windows": # Windows
                plt.rc('font', family='Malgun Gothic')
            plt.rc('axes', unicode_minus=False)
            
            MATPLOTLIB_AVAILABLE = True
        except ImportError:
            MATPLOTLIB_AVAILABLE = False
            messagebox.showerror("오류", "Matplotlib 라이브러리를 로드할 수 없습니다.")
            return

        if not MATPLOTLIB_AVAILABLE:
            messagebox.showerror("Error", "Matplotlib not installed")
            return
            
        # Create Toplevel
        top = ctk.CTkToplevel(self)
        top.title("통계 및 기록 관리")
        top.geometry("700x550")
        top.configure(fg_color=COLOR_BG)
        self.bring_window_front(top)

        # Filters
        filter_frame = ctk.CTkFrame(top, fg_color=COLOR_BG)
        filter_frame.pack(fill="x", padx=10, pady=10)
        
        # Segmented Button for Time
        self.stats_days_var = ctk.StringVar(value="전체")
        
        def update_graph(value):
            days = None
            if value == "최근 1달": days = 30
            elif value == "이번 주": days = 7
            draw_stats(days)

        seg_button = ctk.CTkSegmentedButton(
            filter_frame,
            values=["전체", "최근 1달", "이번 주"],
            command=update_graph,
            variable=self.stats_days_var,
            selected_color=COLOR_ACCENT,
            selected_hover_color="#2563EB",
            unselected_color=COLOR_FRAME,       # Bright White
            unselected_hover_color="#F3F4F6",   # Soft Gray
            fg_color=COLOR_BORDER,              # Container color (Light Gray)
            text_color=COLOR_TEXT_MAIN,
            font=ctk.CTkFont(family="AppleGothic", size=12)
        )
        seg_button.pack(side="left", padx=10)
        
        # Delete Button
        def delete_today():
            if messagebox.askyesno("기록 삭제", "오늘 먹은 점심 기록을 삭제하시겠습니까?"):
                success = self.history.delete_todays_record()
                if success:
                    messagebox.showinfo("성공", "삭제되었습니다.")
                    draw_stats(None) # Refresh (default to All or keep current?) -> simplest is refresh
                    self.stats_days_var.set("전체") # Reset filter
                else:
                    messagebox.showerror("실패", "오늘 기록된 데이터가 없습니다.")

        btn_delete = ctk.CTkButton(filter_frame, text="오늘 기록 취소/삭제", fg_color="#FEE2E2", hover_color="#FECACA", text_color=COLOR_DANGER,
                                   command=delete_today, width=120, font=ctk.CTkFont(family="AppleGothic", size=12))
        btn_delete.pack(side="right", padx=10)

        # TabView (Make it bright!)
        self.tab_view = ctk.CTkTabview(
            top, 
            fg_color=COLOR_BG, 
            text_color=COLOR_TEXT_MAIN,
            segmented_button_fg_color=COLOR_BORDER,           # Container: Light Gray
            segmented_button_selected_color=COLOR_ACCENT,     # Active: Blue
            segmented_button_selected_hover_color="#2563EB",
            segmented_button_unselected_color=COLOR_FRAME,    # Inactive: White
            segmented_button_unselected_hover_color="#F3F4F6"
        )
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)
        
        tab_graphs = self.tab_view.add("차트")
        tab_logs = self.tab_view.add("상세 기록")

        # Function to redraw everything (graphs AND logs)
        def draw_stats(days):
            # 1. Draw Graphs
            for widget in tab_graphs.winfo_children():
                widget.destroy()

            area_counts, cat_counts = self.history.get_stats(days=days)
            
            if not area_counts:
                ctk.CTkLabel(tab_graphs, text="선택한 기간에 데이터가 없습니다.", font=ctk.CTkFont(family="AppleGothic", size=14)).pack(expand=True)
            else:
                # Modern Graph Style
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6, 4))
                fig.patch.set_facecolor('#F3F4F6') # Match modern bg
                
                def style_ax(ax, title):
                    ax.set_facecolor('#F3F4F6')
                    ax.set_title(title, color='#1F2937', fontfamily='AppleGothic', fontsize=12, pad=10)
                    
                style_ax(ax1, "구역별")
                # Pie chart with calm colors
                colors_pie = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
                wedges, texts, autotexts = ax1.pie(area_counts.values(), labels=area_counts.keys(), autopct='%1.1f%%', colors=colors_pie[:len(area_counts)], textprops={'color':"#1F2937", 'family':'AppleGothic'})
                
                style_ax(ax2, "메뉴별 (Top 5)")
                top_cats = cat_counts.most_common(5)
                labels = [x[0] for x in top_cats]
                sizes = [x[1] for x in top_cats]
                wedges, texts, autotexts = ax2.pie(sizes, labels=labels, autopct='%1.1f%%', colors=colors_pie[:len(sizes)], textprops={'color':"#1F2937", 'family':'AppleGothic'})

                canvas = FigureCanvasTkAgg(fig, master=tab_graphs)
                canvas.draw()
                canvas.get_tk_widget().pack(fill="both", expand=True)

            # 2. Draw Logs
            for widget in tab_logs.winfo_children():
                widget.destroy()
            
            records = self.history.get_records(days=days)
            if not records:
                ctk.CTkLabel(tab_logs, text="기록이 없습니다.", font=ctk.CTkFont(family="AppleGothic", size=14)).pack(pady=20)
            else:
                # Scrollable Frame for list
                scroll_frame = ctk.CTkScrollableFrame(tab_logs, fg_color="transparent")
                scroll_frame.pack(fill="both", expand=True)
                
                # Header
                header_frame = ctk.CTkFrame(scroll_frame, fg_color=COLOR_BG)
                header_frame.pack(fill="x", pady=2)
                ctk.CTkLabel(header_frame, text="날짜", width=100, font=ctk.CTkFont(family="AppleGothic", size=12, weight="bold"), text_color=COLOR_TEXT_DIM).pack(side="left", padx=5)
                ctk.CTkLabel(header_frame, text="메뉴", width=150, font=ctk.CTkFont(family="AppleGothic", size=12, weight="bold"), text_color=COLOR_TEXT_DIM).pack(side="left", padx=5)
                ctk.CTkLabel(header_frame, text="분류", width=100, font=ctk.CTkFont(family="AppleGothic", size=12, weight="bold"), text_color=COLOR_TEXT_DIM).pack(side="left", padx=5)
                ctk.CTkLabel(header_frame, text="구역", width=120, font=ctk.CTkFont(family="AppleGothic", size=12, weight="bold"), text_color=COLOR_TEXT_DIM).pack(side="left", padx=5)

                # Rows
                for row in records:
                    row_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
                    row_frame.pack(fill="x", pady=1)
                    # Data: date, menu_name, area, category
                    # CSV keys: date, menu_name, area, category
                    ctk.CTkLabel(row_frame, text=row['date'], width=100, font=ctk.CTkFont(family="AppleGothic", size=11), text_color=COLOR_TEXT_DIM).pack(side="left", padx=5)
                    ctk.CTkLabel(row_frame, text=row['menu_name'], width=150, font=ctk.CTkFont(family="AppleGothic", size=11), text_color=COLOR_TEXT_DIM).pack(side="left", padx=5)
                    ctk.CTkLabel(row_frame, text=row['category'], width=100, font=ctk.CTkFont(family="AppleGothic", size=11), text_color=COLOR_TEXT_DIM).pack(side="left", padx=5)
                    ctk.CTkLabel(row_frame, text=row['area'], width=120, font=ctk.CTkFont(family="AppleGothic", size=11), text_color=COLOR_TEXT_DIM).pack(side="left", padx=5)

        # Initial draw
        draw_stats(None)

    def show_help(self):
        msg = """[날씨 기능] ☀️
- 실시간으로 서울의 날씨와 기온을 가져옵니다.
- 기온이 28°C 이상이면 '더움' 상태가 되어, 뜨거운 국물 요리 추천이 줄어듭니다.
- 비/눈/흐림 날씨에는 국물 요리 추천 확률이 올라갑니다.

[기분 점수] 🤔
기분에 따라 메뉴 추천 확률이 달라집니다.
- 화남 😡: 매운 음식(+5점), 헤비한 음식(+3점)
- 행복 🥰: 고기 요리(+5점)
- 우울 😢: 헤비(+3점), 고기(+3점), 매운거(+3점)
- 피곤 😫: 밥(+4점), 고기(+4점)

(기본 점수 10점에 위 가중치가 더해져서 확률이 계산됩니다)"""
        
        # Using a custom Toplevel for better readability than standard messagebox
        top = ctk.CTkToplevel(self)
        top.title("점심 추천 도우미 - 도움말")
        top.geometry("400x500")
        self.bring_window_front(top)
        
        lbl = ctk.CTkLabel(top, text=msg, justify="left", wraplength=350, font=("", 14))
        lbl.pack(padx=20, pady=20, fill="both", expand=True)
        
        ctk.CTkButton(top, text="닫기", command=top.destroy).pack(pady=20)

if __name__ == "__main__":
    app = App()
    app.mainloop()
