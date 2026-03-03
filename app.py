# app.py
import streamlit as st
import os
import json
import tempfile
import pandas as pd
from PIL import Image
import base64
from datetime import datetime

# --- IMPORT MODULES ---
from config import DEFAULT_SCHEMA_DEFINITION, DEFAULT_FILTER_PRESETS, get_sheet_name, get_rejected_sheet_name, get_spreadsheet_id
from settings_manager import SettingsManager
from ade_extractor import extract_schema_from_file
from google_sheets import get_service_creds, append_values_to_sheet, get_sheet_as_dataframe, update_sheet_from_dataframe
from json_to_csv import build_data_for_sheet

try:
    from career_api import get_job_details, convert_jd_to_filter, fetch_all_active_jobs
except ImportError:
    st.error("Thiếu file career_api.py. Vui lòng tạo file này trước.")
    st.stop()

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="INNO CV Parse Tool",
    page_icon="assets/app_icon.ico",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- LOAD SETTINGS ---
settings_mgr = SettingsManager()

# --- CSS CUSTOM ---
st.markdown("""
<style>
    @import url('https://fonts.cdnfonts.com/css/sf-pro-display');
    html, body, [class*="css"] { font-family: 'SF Pro Display', sans-serif; }
    .gradient-text {
        background: linear-gradient(to right, #0056D2, #9436de, #de3687, #ff6600);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
        font-size: 2.5rem;
        padding-bottom: 10px;
    }
    div.stButton > button {
        background-color: white; color: black; border: 1px solid #4287f5;
        border-radius: 8px; font-weight: 600; transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        background-color: #4287f5; color: white; border-color: #4287f5;
    }
</style>
""", unsafe_allow_html=True)

# --- HÀM LOGIC BỔ TRỢ ---
def normalize_text(text):
    import unicodedata
    if not text: return ""
    text = str(text).lower()
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('utf-8')
    return text

def extract_number(value):
    import re
    if isinstance(value, (int, float)): return float(value)
    if not value: return 0.0
    match = re.search(r"(\d+(\.\d+)?)", str(value).replace(",", "."))
    return float(match.group(1)) if match else 0.0

def validate_cv(cv_data, filter_rules):
    """
    Validate CV dựa trên bộ lọc động từ API (filter_rules)
    """
    if not filter_rules: return True, "Không có bộ lọc (Pass mặc định)"
    
    must = filter_rules.get("must", {})
    plus = filter_rules.get("plus", {})

    # Chuẩn hóa dữ liệu CV
    school = normalize_text(cv_data.get("education_university", ""))
    degree = normalize_text(cv_data.get("education_degree", ""))
    major = normalize_text(cv_data.get("education_major", ""))
    exp = extract_number(cv_data.get("total_experience_years") or cv_data.get("so_nam_kn") or 0)
    salary = extract_number(cv_data.get("salary_expected") or 0)
    
    full_text = (str(cv_data.get("software_skills", "")) + " " + 
                 str(cv_data.get("hard_skills", "")) + " " + 
                 str(cv_data.get("certifications", "")) + " " +
                 str(cv_data.get("languages", ""))).lower()

    # 1. CHECK MUST
    if exp < must.get("min_exp", 0): 
        return False, f"LOẠI: Thiếu KN ({exp} < {must.get('min_exp')} năm)"
    
    max_sal = must.get("max_salary", 0)
    if max_sal > 0 and salary > max_sal: 
        return False, f"LOẠI: Lương cao ({salary} > {max_sal}tr)"

    req_degrees = must.get("degree", [])
    if req_degrees:
        has_d = any(normalize_text(d) in degree for d in req_degrees)
        if not has_d and "dai hoc" not in school: 
            return False, "LOẠI: Sai bằng cấp"

    for kw in must.get("keywords", []):
        if normalize_text(kw) not in normalize_text(full_text): 
            return False, f"LOẠI: Thiếu từ khóa '{kw}'"

    return True, "ĐẠT - Đủ tiêu chuẩn JD"

# --- INIT SESSION STATES ---
if 'selected_job_data' not in st.session_state: st.session_state.selected_job_data = None
if 'processed_data' not in st.session_state: st.session_state.processed_data = []
if 'process_log' not in st.session_state: st.session_state.process_log = []

def log(msg): 
    st.session_state.process_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# --- SIDEBAR ---
# --- SIDEBAR ---
with st.sidebar:
    if os.path.exists("assets/logo.png"):
        st.image("assets/logo.png", width=150)
        
    st.title("Settings")
    
    # 1. LandingAI Key
    with st.expander("🤖 LandingAI API Key", expanded=not settings_mgr.get("ade_api_key")):
        api_key_input = st.text_input("Enter LandingAI Key", value=settings_mgr.get("ade_api_key", ""), type="password")
        if st.button("Save AI Key"):
            settings_mgr.update("ade_api_key", api_key_input)
            settings_mgr.save_settings()
            st.success("Saved!")
            st.rerun()

    # 2. Career API Key
    with st.expander("🔗 Career API Configuration", expanded=not settings_mgr.get("career_api_key")):
        career_api_key = st.text_input("Enter Career API Key", value=settings_mgr.get("career_api_key", ""), type="password")
        if st.button("Save Career Key"):
            settings_mgr.update("career_api_key", career_api_key)
            settings_mgr.save_settings()
            st.success("Saved!")
            st.rerun()

# --- MAIN UI ---
col_head1, col_head2 = st.columns([1, 4])
with col_head1:
    if os.path.exists("assets/logo.png"): st.image("assets/logo.png", width=120)
with col_head2:
    st.markdown('<div class="gradient-text">INNO CV Parse Tool</div>', unsafe_allow_html=True)

# CHECK KEYS
if not settings_mgr.get("ade_api_key"):
    st.error("⚠️ Vui lòng nhập LandingAI API Key trong Sidebar để Scan CV.")
    st.stop()

if not settings_mgr.get("career_api_key"):
    st.warning("⚠️ Vui lòng nhập Career API Key trong Sidebar để tải Job.")
    st.stop()

# TẠO TABS CHÍNH
tab_scan, tab_manage = st.tabs(["🚀 Scan & Upload CV", "✏️ Quản lý & Sửa lỗi (Google Sheets)"])

# ==========================================
# TAB 1: SCAN & UPLOAD
# ==========================================
with tab_scan:
    # st.markdown("---")
    col_job_select, col_job_info = st.columns([1, 2])
    current_filter = None

    with col_job_select:
        st.subheader("1. Chọn Job (Từ API)")
        tab_list, tab_id = st.tabs(["Danh sách Active", "Nhập ID Job"])
        
        with tab_list:
            if st.button("🔄 Tải danh sách Job đang tuyển"):
                api_key = settings_mgr.get("career_api_key")
                with st.spinner("Đang tải danh sách..."):
                    jobs_list, msg = fetch_all_active_jobs(api_key)
                    if jobs_list is not None:
                        st.session_state['api_jobs_cache'] = jobs_list
                        st.success(f"✅ Tải thành công {len(jobs_list)} Job!")
                    else:
                        st.error(f"❌ Lỗi: {msg}")

            if st.session_state.get('api_jobs_cache'):
                job_map = {f"{j['title']}": j for j in st.session_state['api_jobs_cache']}
                selected_name = st.selectbox("Chọn Job:", list(job_map.keys()))
                if selected_name:
                    st.session_state.selected_job_data = job_map[selected_name]

        with tab_id:
            job_id_input = st.text_input("Nhập Job ID (VD: telox8TfIdc9p9hCuN1D)", placeholder="job_id...")
            if st.button("🔍 Tải JD theo ID"):
                if job_id_input:
                    job_data = get_job_details(job_id_input, settings_mgr.get("career_api_key"))
                    if job_data:
                        st.session_state.selected_job_data = job_data
                        st.success("Tải Job thành công!")
                    else:
                        st.error("Không tìm thấy Job ID này.")

    # Hiển thị thông tin Job & Tạo Filter
    with col_job_info:
        job_data = st.session_state.selected_job_data
        if job_data:
            st.success(f"✅ Đang chọn: **{job_data.get('title')}**")
            
            # Tạo filter từ JD
            current_filter = convert_jd_to_filter(job_data)
            
            with st.expander("👀 Xem tiêu chí lọc (Tự động từ JD)", expanded=True):
                must = current_filter['must']
                st.markdown(f"""
                * **Kinh nghiệm:** > {must['min_exp']} năm
                * **Lương tối đa:** {must['max_salary']} triệu
                * **Từ khóa (Tags):** {', '.join(must['keywords'])}
                * **Bằng cấp:** {', '.join(must['degree']) if must['degree'] else 'Tùy chọn'}
                """)
        else:
            st.info("👈 Vui lòng chọn Job ở bên trái để lấy tiêu chí lọc.")

    # KHU VỰC UPLOAD
    st.markdown("---")
    st.subheader("2. Upload & Scan CV")
    uploaded_files = st.file_uploader("Chọn file PDF/DOCX", type=['pdf', 'docx'], accept_multiple_files=True)

    col_btn1, col_btn2, col_btn3 = st.columns(3)

    # Nút: SCAN AI
    with col_btn1:
        btn_disabled = not uploaded_files or not current_filter
        if st.button("🤖 Scan with AI", width='stretch', disabled=btn_disabled):
            st.session_state.processed_data = []
            st.session_state.process_log = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Đang xử lý {uploaded_file.name}...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp:
                    tmp.write(uploaded_file.getvalue())
                    tmp_path = tmp.name
                
                try:
                    res = extract_schema_from_file(tmp_path)
                    res["job_position"] = st.session_state.selected_job_data.get('title', 'Unknown')
                    res["source_file"] = uploaded_file.name
                    
                    is_pass, reason = validate_cv(res, current_filter)
                    res["ghi_chu_app"] = reason
                    res["is_pass"] = is_pass
                    
                    st.session_state.processed_data.append(res)
                    log(f"✅ {uploaded_file.name}: {reason}")
                except Exception as e:
                    log(f"❌ Lỗi {uploaded_file.name}: {str(e)}")
                finally:
                    os.remove(tmp_path)
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            status_text.text("Hoàn tất Scan!")

    # Nút: UPLOAD SHEET
    with col_btn2:
        if st.button("☁️ Upload Google Sheet", width='stretch', disabled=not st.session_state.processed_data):
            creds = get_service_creds()
            schema = settings_mgr.get("schema_definition", DEFAULT_SCHEMA_DEFINITION)
            pass_list = [cv for cv in st.session_state.processed_data if cv.get("is_pass", False)]
            fail_list = [cv for cv in st.session_state.processed_data if not cv.get("is_pass", False)]
            
            try:
                if pass_list:
                    h, d = build_data_for_sheet(pass_list, "Admin", schema)
                    append_values_to_sheet(h, d, creds, get_sheet_name(), get_spreadsheet_id())
                    st.toast(f"Đã upload {len(pass_list)} CV Đạt", icon="✅")
                if fail_list:
                    h, d = build_data_for_sheet(fail_list, "Admin", schema)
                    append_values_to_sheet(h, d, creds, get_rejected_sheet_name(), get_spreadsheet_id())
                    st.toast(f"Đã upload {len(fail_list)} CV Loại", icon="⚠️")
                log("Upload hoàn tất.")
            except Exception as e:
                st.error(f"Lỗi Upload: {e}")

    # Nút: OPEN SHEET
    with col_btn3:
        sheet_url = f"https://docs.google.com/spreadsheets/d/{get_spreadsheet_id()}/edit"
        st.link_button("📄 Mở Google Sheet", sheet_url, width='stretch')

    # Hiển thị kết quả
    st.markdown("---")
    col_res1, col_res2 = st.columns(2)
    with col_res1:
        st.subheader("Kết quả trích xuất")
        if st.session_state.processed_data:
            st.json(st.session_state.processed_data, expanded=False)
        else:
            st.info("Chưa có dữ liệu.")
    with col_res2:
        st.subheader("Log hoạt động")
        log_text = "\n".join(st.session_state.process_log)
        st.text_area("Log", log_text, height=400)

# ==========================================
# TAB 2: QUẢN LÝ & SỬA LỖI TRÊN GG SHEETS
# ==========================================
with tab_manage:
    st.header("Chỉnh sửa dữ liệu trực tiếp trên Google Sheet")
    st.info("💡 Tính năng này giúp bạn sửa nhanh các lỗi (sai email, thiếu sđt...) mà AI nhận diện sai. Nhấn 'Cập nhật' để lưu lại lên Sheet gốc.")

    sheet_option = st.radio("Chọn Sheet dữ liệu:", ["CV Đạt (Admin)", "CV Loại (Rejected)"], horizontal=True)
    target_sheet_name = get_sheet_name() if sheet_option == "CV Đạt (Admin)" else get_rejected_sheet_name()
    spreadsheet_id = get_spreadsheet_id()
    
    if st.button("🔄 Tải dữ liệu hiện tại từ Sheet"):
        try:
            creds = get_service_creds()
            df = get_sheet_as_dataframe(creds, spreadsheet_id, target_sheet_name)
            st.session_state['editing_df'] = df
            st.session_state['current_sheet_name'] = target_sheet_name
            st.success(f"Đã tải {len(df)} dòng dữ liệu.")
        except Exception as e:
            st.error(f"Lỗi tải dữ liệu: {e}")

    if 'editing_df' in st.session_state and not st.session_state['editing_df'].empty:
        if st.session_state.get('current_sheet_name') == target_sheet_name:
            # Data Editor
            edited_df = st.data_editor(
                st.session_state['editing_df'], 
                num_rows="dynamic",
                width='stretch',
                height=500
            )
            
            col_save, col_cancel = st.columns([1, 4])
            with col_save:
                if st.button("💾 Lưu thay đổi lên Sheet", type="primary"):
                    try:
                        creds = get_service_creds()
                        update_sheet_from_dataframe(creds, spreadsheet_id, target_sheet_name, edited_df)
                        st.toast("Cập nhật dữ liệu thành công!", icon="✅")
                        st.session_state['editing_df'] = edited_df 
                    except Exception as e:
                        st.error(f"Lỗi cập nhật: {e}")
            with col_cancel:
                if st.button("Hủy bỏ"):
                    del st.session_state['editing_df']
                    st.rerun()
        else:
            st.warning("⚠️ Bạn đã chuyển Sheet. Vui lòng nhấn 'Tải dữ liệu hiện tại' lại để tránh ghi đè nhầm dữ liệu.")
    elif 'editing_df' in st.session_state:
        st.warning("Sheet này hiện chưa có dữ liệu.")