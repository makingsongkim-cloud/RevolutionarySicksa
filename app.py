import streamlit as st
import lunch_data
import recommender
from history_manager import LunchHistory
import pandas as pd
import time

# Page Config
st.set_page_config(
    page_title="Revolutionary Sicksa",
    page_icon="🍱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Logic Classes
if 'recommender' not in st.session_state:
    st.session_state.recommender = recommender.LunchRecommender()
if 'history' not in st.session_state:
    st.session_state.history = LunchHistory()

# Custom CSS for styling and animation
st.markdown("""
<style>
    @keyframes spin3d {
        0% { 
            transform: rotateY(0deg);
        }
        100% { 
            transform: rotateY(1620deg);
        }
    }
    
    .flip-container {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 450px;
        height: 450px;
        z-index: 9999;
        perspective: 1500px;
    }
    
    .flipper {
        position: relative;
        width: 100%;
        height: 100%;
        transform-style: preserve-3d;
        transition: transform 0.6s;
    }
    
    .flipper.spinning {
        animation: spin3d 2s ease-in-out forwards;
    }
    
    .flipper.show-back {
        transform: rotateY(180deg);
    }
    
    .flip-front, .flip-back {
        position: absolute;
        width: 100%;
        height: 100%;
        backface-visibility: hidden;
        -webkit-backface-visibility: hidden;
        border-radius: 50%;
        box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    }
    
    .flip-front {
        transform: rotateY(0deg);
    }
    
    .flip-back {
        transform: rotateY(180deg);
    }
    
    .flip-front img, .flip-back img {
        width: 100%;
        height: 100%;
        border-radius: 50%;
    }
    
    .big-font {
        font-size:30px !important;
        font-weight: bold;
        color: #1F2937;
    }
    .medium-font {
        font-size:20px !important;
        color: #4B5563;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        font-weight: bold;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Auto-Fetch Weather (Silent) ---
if 'weather_info' not in st.session_state:
    # 1. Try Config / Auto Detect
    cfg = lunch_data.load_config()
    target = cfg.get("location")
    
    if not target:
        target = st.session_state.recommender.detect_city_by_ip() or "Seoul"
        lunch_data.save_config({"location": target})

    # 2. Fetch
    cond, temp = st.session_state.recommender.get_weather(location=target)
    if cond is None:
         cond, temp = st.session_state.recommender.get_weather(location="Seoul")
    
    st.session_state.weather_info = (cond, temp, target)

# Unpack weather
w_cond, w_temp, w_loc = st.session_state.weather_info

# --- Sidebar (Clean Info) ---
with st.sidebar:
    st.title("🍱 지존 마스터님")
    
    # User Nickname Input
    nickname = st.text_input("닉네임 (기록용)", value="", placeholder="예: 홍길동", help="이 이름을 기준으로 식사 기록이 저장됩니다.")
    # 빈칸이면 기본값 사용
    if not nickname.strip():
        nickname = "사용자"
    st.session_state.user_nickname = nickname
    
    st.markdown("---")
    st.subheader("📍 현재 상황")
    
    # Safe Display
    disp_cond = w_cond if w_cond else "맑음(기본)"
    disp_temp = w_temp if w_temp else "20°C"
    st.info(f"**{w_loc}**\n\n{disp_cond} {disp_temp}")
    
    st.markdown("---")
    with st.expander("🔧 관리자 설정"):
        admin_pwd = st.text_input("관리자 암호", type="password", key="admin_pw_input")
        if admin_pwd == "2545":
            st.session_state.is_admin = True
            st.success("관리자 권한: 활성화됨")
        else:
            st.session_state.is_admin = False

# --- Main Content ---
# --- Main Content ---
st.title(f"🍱 {nickname}님, 식사하시죠")

# Define Tabs dynamically
tabs_labels = ["🍽️ 메뉴 추천", "🎡 밥상 돌리기", "📊 통계/기록", "✍️ 수동 기록"]
if st.session_state.get("is_admin", False):
    tabs_labels.append("📝 데이터 관리")

tabs = st.tabs(tabs_labels)
tab1, tab2, tab3, tab4 = tabs[0], tabs[1], tabs[2], tabs[3]
tab5 = tabs[4] if len(tabs) > 4 else None

# ... (Tab 1, 2, 3 content remains same, implicit via context but user didn't ask to change them) ... 

# I need to target Tab 4 and Tab 5 blocks specifically to avoid overwriting everything. 
# But this tool replaces a block. I will target the Tab definition line first.


# --- TAB 1: Recommendation ---
with tab1:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("취향 선택")
        
        # Cuisine Filter
        st.markdown("**어떤 종류가 땡기시나요?**")
        cuisines = [
            lunch_data.CUISINE_KOREAN, lunch_data.CUISINE_CHINESE, 
            lunch_data.CUISINE_JAPANESE, lunch_data.CUISINE_WESTERN, 
            lunch_data.CUISINE_SNACK
        ]
        
        selected_cuisines = []
        for c in cuisines:
            if st.checkbox(c, value=False):
                selected_cuisines.append(c)
        
        st.markdown("---")
        
        # Mood Select
        st.markdown("**양자택일: 오늘 기분은?**")
        mood = st.selectbox("기분", ["보통", "화남", "행복", "우울", "피곤"], label_visibility="collapsed")
        
    with col2:
        st.subheader("오늘의 추천 메뉴")
        
        # Spacer
        st.write("")
        st.write("")
        
        if st.button("🎲 메뉴 추천받기", type="primary"):
            filters = selected_cuisines if selected_cuisines else None
            rec = st.session_state.recommender.recommend(weather=w_cond, cuisine_filters=filters, mood=mood)
            st.session_state.current_rec = rec
        
        # Result Display
        if 'current_rec' in st.session_state and st.session_state.current_rec:
            rec = st.session_state.current_rec
            
            st.success("짜잔! 이 메뉴 어떠세요? 👇")
            
            st.markdown(f'<p class="big-font">{rec["name"]}</p>', unsafe_allow_html=True)
            st.markdown(f'<p class="medium-font">{rec["category"]} | {rec["area"]}</p>', unsafe_allow_html=True)
            
            # Action Button (결정만 가능, 다시 추천은 위의 버튼 재사용)
            if st.button("👍 이걸로 결정! (기록 저장)"):
                st.session_state.history.save_record(rec['name'], rec['area'], rec['category'], user=nickname)
                st.balloons()
                st.toast(f"'{rec['name']}' 식사가 기록되었습니다!", icon="✅")

# --- TAB 2: Table Spin (Random Game) ---
with tab2:
    st.subheader("🌀 운명의 밥상 돌리기")
    st.info("오늘 점심은 운에 맡기세요!")
    
    spin_mode = st.radio("모드 선택", ["전체 메뉴 뺑뺑이", "내가 고른 후보만"], horizontal=True)
    
    all_menus = lunch_data.load_menus()
    
    if spin_mode == "전체 메뉴 뺑뺑이":
        # 세션 상태 초기화
        if 'spin_step' not in st.session_state:
            st.session_state.spin_step = 'ready'
            st.session_state.spin_picked = None
        
        if st.session_state.spin_step == 'ready':
            if st.button("🚀 밥상 돌리기 시작!", type="primary", key="start_spin_all"):
                import random
                
                # 중복 방지: 최근 3개 선택 항목 제외
                if 'recent_picks' not in st.session_state:
                    st.session_state.recent_picks = []
                
                available_menus = [m for m in all_menus if m['name'] not in st.session_state.recent_picks]
                
                # 선택 가능한 메뉴가 없으면 기록 초기화
                if not available_menus:
                    st.session_state.recent_picks = []
                    available_menus = all_menus
                
                # Pick Winner
                picked = random.choice(available_menus)
                st.session_state.spin_picked = picked
                
                # 최근 선택 항목 기록 (최대 3개 유지)
                st.session_state.recent_picks.append(picked['name'])
                if len(st.session_state.recent_picks) > 3:
                    st.session_state.recent_picks.pop(0)
                
                st.session_state.spin_step = 'spinning'
                st.rerun()
        
        elif st.session_state.spin_step == 'spinning':
            import base64
            from PIL import Image, ImageDraw, ImageFont
            import io
            
            picked = st.session_state.spin_picked
            
            # Load Front Image
            try:
                with open("table_front_transparent.png", "rb") as f:
                    front_data = f.read()
                    table_front = base64.b64encode(front_data).decode()
            except:
                table_front = ""
            
            # Create Back Image (텍스트 없이 이미지만 생성)
            try:
                # 뒷면 이미지 동적 생성
                img = Image.new('RGB', (900, 900), (224, 224, 224))
                draw = ImageDraw.Draw(img)
                
                # 원형 테이블 밑면 (깔끔하게)
                draw.ellipse((0, 0, 900, 900), fill=(101, 67, 33))
                
                # PNG로 변환
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                table_back = base64.b64encode(buffer.getvalue()).decode()
            except Exception as e:
                print(f"뒷면 이미지 생성 중 치명적 오류: {e}") 
                table_back = ""

            # Animation: 3D Flip Card
            if table_front and table_back:
                # 텍스트는 Python이 아니라 CSS로 띄웁니다 (폰트 깨짐 방지)
                menu_name = picked['name']
                
                st.markdown(f'''
                    <style>
                        .menu-name-overlay {{
                            position: absolute;
                            top: 50%;
                            left: 50%;
                            transform: translate(-50%, -50%) rotateY(180deg); /* 뒷면에 맞춰 뒤집기 */
                            font-size: 80px; 
                            font-weight: 900;
                            color: white;
                            text-align: center;
                            width: 80%;
                            z-index: 10;
                            text-shadow: 
                                -2px -2px 0 #000,  
                                2px -2px 0 #000,
                                -2px 2px 0 #000,
                                2px 2px 0 #000, /* 얇은 외곽선 */
                                4px 4px 8px rgba(0,0,0,0.5); /* 그림자 */
                            font-family: "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
                            word-break: keep-all;
                            line-height: 1.2;
                        }}
                    </style>
                    <div class="flip-container">
                        <div class="flipper spinning">
                            <div class="flip-front">
                                <img src="data:image/png;base64,{table_front}">
                            </div>
                            <div class="flip-back">
                                <img src="data:image/png;base64,{table_back}">
                                <div class="menu-name-overlay">{menu_name}</div>
                            </div>
                        </div>
                    </div>
                    <script>
                    // 아무 곳이나 클릭하거나 키보드 누르면 결과 보기 버튼 자동 클릭
                    setTimeout(function() {{
                        function autoClick() {{
                            const btn = document.querySelector('button[kind="primary"]');
                            if (btn && btn.innerText.includes('결과 보기')) {{
                                btn.click();
                            }}
                            // 이벤트 제거
                            document.removeEventListener('click', autoClick);
                            document.removeEventListener('keydown', autoClick);
                        }}
                        
                        // 클릭 이벤트 리스너
                        document.addEventListener('click', autoClick);
                        // 키보드 이벤트 리스너
                        document.addEventListener('keydown', autoClick);
                    }}, 2000); // 2초 후 (애니메이션 완료 후)
                    </script>
                ''', unsafe_allow_html=True)
            else:
                st.markdown('<div class="spinning-emoji">🥘</div>', unsafe_allow_html=True)
            
            # 사용자가 클릭해야 다음으로
            st.markdown("<br>" * 15, unsafe_allow_html=True)
            if st.button("⏸️ 결과 보기 (클릭)", type="primary", key="show_result_all"):
                st.session_state.spin_step = 'result'
                st.rerun()
        
        elif st.session_state.spin_step == 'result':
            picked = st.session_state.spin_picked
            st.success("🎉 당첨!")
            st.balloons()
            st.markdown(f'<p class="big-font">{picked["name"]}</p>', unsafe_allow_html=True)
            st.caption(f"{picked['category']} | {picked['area']}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("이걸로 결정 (저장)", key="spin_save_all"):
                    st.session_state.history.save_record(picked['name'], picked['area'], picked['category'], user=nickname)
                    st.toast("저장되었습니다!", icon="✅")
                    st.session_state.spin_step = 'ready'
                    st.rerun()
            with col2:
                if st.button("🔄 다시 돌리기", key="spin_again_all"):
                    st.session_state.spin_step = 'ready'
                    st.rerun()

    else: # Custom Candidates
        menu_names = [m["name"] for m in all_menus]
        candidates = st.multiselect("후보를 골라주세요 (최소 2개)", menu_names, key="custom_candidates")
        
        if len(candidates) < 2:
            st.warning("후보를 2개 이상 선택해야 밥상을 돌릴 수 있습니다.")
        else:
            # 세션 상태 초기화
            if 'spin_custom_step' not in st.session_state:
                st.session_state.spin_custom_step = 'ready'
                st.session_state.spin_custom_picked = None
            
            if st.session_state.spin_custom_step == 'ready':
                if st.button("🚀 선택한 후보로 돌리기", type="primary", key="start_spin_custom"):
                    import random
                    
                    # 중복 방지: 최근 3개 선택 항목 제외
                    if 'recent_custom_picks' not in st.session_state:
                        st.session_state.recent_custom_picks = []
                    
                    available_candidates = [c for c in candidates if c not in st.session_state.recent_custom_picks]
                    
                    # 선택 가능한 후보가 없으면 기록 초기화
                    if not available_candidates:
                        st.session_state.recent_custom_picks = []
                        available_candidates = candidates
                    
                    # Pick Winner
                    winner_name = random.choice(available_candidates)
                    st.session_state.spin_custom_picked = next((m for m in all_menus if m["name"] == winner_name), None)
                    
                    # 최근 선택 항목 기록 (최대 3개 유지)
                    st.session_state.recent_custom_picks.append(winner_name)
                    if len(st.session_state.recent_custom_picks) > 3:
                        st.session_state.recent_custom_picks.pop(0)
                    
                    st.session_state.spin_custom_step = 'spinning'
                    st.rerun()
            
            elif st.session_state.spin_custom_step == 'spinning':
                import base64
                from PIL import Image, ImageDraw, ImageFont
                import io
                
                winner = st.session_state.spin_custom_picked
                
                # Load Front Image
                try:
                    with open("table_front_transparent.png", "rb") as f:
                        front_data = f.read()
                        table_front = base64.b64encode(front_data).decode()
                except:
                    table_front = ""
                
                # Create Back Image with Menu Name (동적 생성)
                try:
                    # 뒷면 이미지 동적 생성
                    img = Image.new('RGB', (900, 900), (224, 224, 224))
                    draw = ImageDraw.Draw(img)
                    
                    # 원형 테이블 밑면 (깔끔하게, 마크 없이)
                    draw.ellipse((0, 0, 900, 900), fill=(101, 67, 33))
                    
                # Create Back Image (텍스트 없이 이미지만)
                try:
                    img = Image.new('RGB', (900, 900), (224, 224, 224))
                    draw = ImageDraw.Draw(img)
                    draw.ellipse((0, 0, 900, 900), fill=(101, 67, 33))
                    
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    table_back = base64.b64encode(buffer.getvalue()).decode()
                except Exception as e:
                    print(f"뒷면 이미지 생성 중 치명적 오류: {e}")
                    table_back = ""

                # Animation: 3D Flip Card
                if table_front and table_back:
                    menu_name = winner['name']
                    st.markdown(f'''
                        <style>
                            .menu-name-overlay {{
                                position: absolute;
                                top: 50%;
                                left: 50%;
                                transform: translate(-50%, -50%) rotateY(180deg);
                                font-size: 80px; 
                                font-weight: 900;
                                color: white;
                                text-align: center;
                                width: 80%;
                                z-index: 10;
                                text-shadow: 
                                    -2px -2px 0 #000,  
                                    2px -2px 0 #000,
                                    -2px 2px 0 #000,
                                    2px 2px 0 #000,
                                    4px 4px 8px rgba(0,0,0,0.5);
                                font-family: "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
                                word-break: keep-all;
                                line-height: 1.2;
                            }}
                        </style>
                        <div class="flip-container">
                            <div class="flipper spinning">
                                <div class="flip-front">
                                    <img src="data:image/png;base64,{table_front}">
                                </div>
                                <div class="flip-back">
                                    <img src="data:image/png;base64,{table_back}">
                                    <div class="menu-name-overlay">{menu_name}</div>
                                </div>
                            </div>
                        </div>
                        <div class="click-overlay" id="click-overlay"></div>
                        <style>
                            .click-overlay {
                                position: fixed;
                                top: 0;
                                left: 0;
                                width: 100vw;
                                height: 100vh;
                                z-index: 10000; /* 밥상보다 위에 */
                                cursor: pointer;
                                display: none; /* 처음엔 숨김 */
                            }
                        </style>
                        <script>
                        setTimeout(function() {{
                            // 2초 후 오버레이 활성화 (애니메이션 얼추 돌았을 때)
                            const overlay = document.getElementById('click-overlay');
                            if (overlay) {{
                                overlay.style.display = 'block';
                                
                                // 클릭 이벤트
                                overlay.addEventListener('click', function() {{
                                    const btn = document.querySelector('button[kind="primary"]');
                                    // 버튼 텍스트가 '결과 보기'를 포함하는지 확인 (정확도 높임)
                                    // 만약 버튼이 여러개면 loop로 찾기
                                    const btns = document.querySelectorAll('button[kind="primary"]');
                                    for (let b of btns) {{
                                        if (b.innerText.includes('결과 보기')) {{
                                            b.click();
                                            break;
                                        }}
                                    }}
                                }});
                                
                                // 키보드 이벤트 (window 전체)
                                window.addEventListener('keydown', function(e) {{
                                     const btns = document.querySelectorAll('button[kind="primary"]');
                                    for (let b of btns) {{
                                        if (b.innerText.includes('결과 보기')) {{
                                            b.click();
                                            break;
                                        }}
                                    }}
                                }}, {{once: true}});
                            }}
                        }}, 2000);
                        </script>
                    ''', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="spinning-emoji">🥘</div>', unsafe_allow_html=True)
                
                # 사용자가 클릭해야 다음으로
                st.markdown("<br>" * 15, unsafe_allow_html=True)
                if st.button("⏸️ 결과 보기 (클릭)", type="primary", key="show_result_custom"):
                    st.session_state.spin_custom_step = 'result'
                    st.rerun()
            
            elif st.session_state.spin_custom_step == 'result':
                winner = st.session_state.spin_custom_picked
                st.success("🎉 당첨!")
                st.balloons()
                st.markdown(f'<p class="big-font">{winner["name"]}</p>', unsafe_allow_html=True)
                st.caption(f"{winner['category']} | {winner['area']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("이걸로 결정 (저장)", key="spin_save_custom"):
                        st.session_state.history.save_record(winner['name'], winner['area'], winner['category'], user=nickname)
                        st.toast("저장되었습니다!", icon="✅")
                        st.session_state.spin_custom_step = 'ready'
                        st.rerun()
                with col2:
                    if st.button("🔄 다시 돌리기", key="spin_again_custom"):
                        st.session_state.spin_custom_step = 'ready'
                        st.rerun()

# --- TAB 3: Stats ---
with tab3:
    st.subheader(f"📈 {nickname}님의 식사 기록")
    
    days_filter = st.radio("기간 선택", ["전체", "최근 1달", "이번 주"], horizontal=True)
    
    limit = None
    if days_filter == "최근 1달": limit = 30
    elif days_filter == "이번 주": limit = 7
    
    stats_data = st.session_state.history.get_stats(days=limit, user=nickname)
    
    if not stats_data[0] and not stats_data[1]: # Check if both empty
        st.info("아직 기록된 데이터가 충분하지 않습니다.")
    else:
        # Prepare Data for Chart
        chart_data = {"Category": [], "Count": []}
        # Use category stats
        for k, v in stats_data[1].items():
            chart_data["Category"].append(k)
            chart_data["Count"].append(v)
        
        df = pd.DataFrame(chart_data)
        
        st.bar_chart(df, x="Category", y="Count", color="#3B82F6")
        
        with st.expander("📝 상세 기록 보기"):
            logs = st.session_state.history.get_history_logs(days=limit, user=nickname)
            for log in logs:
                st.text(log)
                
    if st.button("🗑️ 오늘 기록 삭제"):
        if st.session_state.history.delete_todays_record(user=nickname):
            st.success("오늘 기록을 삭제했습니다.")
            st.rerun()
        else:
            st.warning("오늘 기록된 내용이 없습니다.")

# --- TAB 4: Manual Record ---
with tab4:
    st.subheader("✍️ 수동 기록 남기기")
    st.caption("메뉴판에 없어도, 내가 먹은 건 기록할 수 있습니다.")
    
    all_menus = lunch_data.load_menus()
    menu_names = [f"{m['name']} ({m['category']})" for m in all_menus]
    menu_names.insert(0, "직접 입력 (메뉴판에 없음)")
    
    selected_manual = st.selectbox("어떤 걸 드셨나요?", menu_names)
    
    final_name = ""
    final_area = "외부/기타"
    final_cat = "기타"
    
    if "직접 입력" in selected_manual:
        col_m1, col_m2, col_m3 = st.columns([2, 1, 1])
        with col_m1:
            final_name = st.text_input("메뉴 이름 (예: 집밥)")
        with col_m2:
            final_cat = st.selectbox("종류", ["한식", "중식", "일식", "양식", "분식", "기타"], index=5)
        with col_m3:
            final_area = st.text_input("위치", value="외부")
    else:
        # Save from existing
        actual_name = selected_manual.split(" (")[0]
        target = next((m for m in all_menus if m["name"] == actual_name), None)
        if target:
            final_name = target['name']
            final_area = target['area']
            final_cat = target['category']

    if st.button("기록 저장하기"):
        if final_name:
            st.session_state.history.save_record(final_name, final_area, final_cat, user=nickname)
            st.success(f"'{final_name}' 기록이 저장되었습니다!")
            time.sleep(1)
            st.rerun()
        else:
            st.error("메뉴 이름을 입력해주세요.")

# --- TAB 5: Manage Data (Admin Only) ---
if tab5:
    with tab5:
        st.subheader("💾 데이터 관리 (관리자 전용)")
        
        tab_m1, tab_m2 = st.tabs(["메뉴 추가", "데이터 목록"])
        
        with tab_m1:
            with st.form("add_menu_form"):
                new_name = st.text_input("식당 이름")
                new_cat = st.selectbox("카테고리", cuisines)
                new_area = st.text_input("위치/특징")
                
                submitted = st.form_submit_button("추가하기")
                if submitted:
                    if new_name and new_area:
                        # lunch_data.save_new_menu(name, area, category, cuisine, tags)
                        # 여기서는 category가 cuisine 역할도 겸하고 있음 (간단 버전)
                        # tags는 임시로 빈 리스트
                        lunch_data.save_new_menu(new_name, new_area, new_cat, new_cat, [])
                        st.session_state.recommender.refresh_data()
                        st.success(f"'{new_name}' 추가 완료!")
                    else:
                        st.error("이름과 위치를 모두 입력해주세요.")
        
        with tab_m2:
            menus = lunch_data.load_menus()
            df_menus = pd.DataFrame(menus)
            st.dataframe(df_menus, use_container_width=True)
            st.caption(f"총 {len(menus)}개의 맛집 데이터가 있습니다.")

