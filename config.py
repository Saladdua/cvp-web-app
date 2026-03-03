# config.py
import sys
import os
import json
from dotenv import load_dotenv

# Tải các biến môi trường từ file .env (chỉ có tác dụng ở local)
load_dotenv()

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# =====================================================
# === CẤU HÌNH BIẾN MÔI TRƯỜNG ===
# =====================================================

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
SHEET_NAME = os.getenv("SHEET_NAME_ACCEPT", "CV_Accept")
SHEET_NAME_REJECTED = os.getenv("SHEET_NAME_REJECT", "CV_Reject") 

# Load Service Account từ biến môi trường dạng JSON String
service_account_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
if service_account_str:
    try:
        # Chuyển đổi chuỗi JSON thành Dictionary, handle ký tự xuống dòng \n trong private_key
        # Thay thế \\n thành \n thực tế để Google API đọc được key
        service_account_str = service_account_str.replace('\\n', '\n')
        SERVICE_ACCOUNT_INFO = json.loads(service_account_str, strict=False)
    except Exception as e:
        print(f"Lỗi đọc GOOGLE_CREDENTIALS_JSON từ .env: {e}")
        SERVICE_ACCOUNT_INFO = {}
else:
    SERVICE_ACCOUNT_INFO = {}

# =====================================================

ADE_PARSE_ENDPOINT = "https://api.va.landing.ai/v1/tools/agentic-document-analysis"
DEFAULT_ADE_PARSE_ENDPOINT = ADE_PARSE_ENDPOINT
DATETIME_FORMAT = "%d/%m/%Y %H:%M"
MAX_PAGES_TO_SCAN = 3
CRITICAL_FIELDS = ["email", "phone"]

# === SCHEMA MỚI (Đã cập nhật theo yêu cầu) ===
DEFAULT_SCHEMA_DEFINITION = [
    # --- THÔNG TIN CÁ NHÂN ---
    {"key": "full_name", "title": "Họ và tên", "description": "Họ và tên đầy đủ của ứng viên."},
    {"key": "date_of_birth", "title": "Ngày sinh", "description": "Ngày tháng năm sinh (định dạng chuyển thành dd/mm/yyyy)."},
    
    # [TỰ ĐỘNG] Cột Tuổi (Được tính toán tự động trong code)
    {"key": "age", "title": "Tuổi", "description": "Tuổi của ứng viên (Tính bằng Năm hiện tại - Năm sinh)."},
    
    {"key": "current_city", "title": "Địa chỉ", "description": "Địa điểm cư trú hiện tại (Tỉnh/TP)."},
    {"key": "email", "title": "Email", "description": "Địa chỉ email liên hệ chính."},
    {"key": "phone", "title": "Số điện thoại", "description": "Số điện thoại liên hệ chính, chuyển về dạng viết liền, bắt đầu bằng số 0 (+84 hay +84- chuyển thành 0)."},
    
    # --- HỌC VẤN (Lấy cái cao nhất) ---
    {"key": "education_degree", "title": "Bằng cấp cao nhất", "description": "Bằng cấp cao nhất (Đại học, Thạc sĩ...)."},
    {"key": "education_major", "title": "Chuyên ngành", "description": "Chuyên ngành đào tạo chính (VD: Kỹ thuật xây dựng, Kiến trúc...)."},
    {"key": "education_university", "title": "Trường Đại học", "description": "Tên trường đào tạo (VD: ĐH Xây dựng, ĐH Kiến trúc...)."},
    {"key": "education_grad_year", "title": "Năm tốt nghiệp", "description": "Năm tốt nghiệp (nếu có, không có thì bỏ trống)."},

    # --- KINH NGHIỆM ---
    # Cập nhật mô tả để AI ưu tiên tính theo Năm cuối - Năm đầu
    {"key": "total_experience_years", "title": "Tổng số năm KN", "description": "Tổng số năm kinh nghiệm. Tính bằng: (Năm làm việc gần nhất hoặc hiện tại) TRỪ ĐI (Năm bắt đầu công việc đầu tiên). Trả về SỐ."},

    # --- KỸ NĂNG & PHẦN MỀM ---
    {"key": "software_skills", "title": "Phần mềm", "description": "Danh sách các phần mềm thành thạo (AutoCAD, Revit, Etabs...). Trả về chuỗi danh sách."},
    {"key": "hard_skills", "title": "Kỹ năng chuyên môn", "description": "Các kỹ năng chuyên môn (triển khai BVTC, tính toán kết cấu...)."},
    
    # --- NGOẠI NGỮ ---
    {"key": "languages", "title": "Ngoại ngữ", "description": "Danh sách ngoại ngữ và trình độ (VD: Tiếng Anh - Tốt, Tiếng Nhật - N3)."},
    
    # --- CHỨNG CHỈ & KHÁC ---
    {"key": "certifications", "title": "Chứng chỉ", "description": "Các chứng chỉ, khóa học chuyên môn (CCHN, BIM, PMP...)."},
    {"key": "salary_expected", "title": "Lương mong muốn", "description": "Mức lương mong muốn (Triệu VNĐ). Trả về SỐ (VD: 15)."},
    {"key": "notes", "title": "Ghi chú ứng viên", "description": "Các ghi chú quan trọng khác (nguyện vọng, mức lương...)."},
    
    # --- CỘT ĐÁNH GIÁ CỦA APP ---
    {"key": "portfolio_link", "title": "Link Portfolio", "description": "Đường link portfolio online (Behance, Drive...)."},
    {"key": "ghi_chu_app", "title": "Đánh giá", "description": "Lý do loại hoặc ghi chú từ App."},

    # --- CỘT STATUS --
    {"key": "status", "title": "Status", "description": "Để trống"},
    {"key": "job_position", "title": "Vị trí ứng tuyển", "description": "Vị trí công việc đang xét duyệt."},
]

# === BỘ LỌC MẶC ĐỊNH (GỘP CHUNG - KHÔNG CÒN PLUS) ===
# Tất cả tiêu chí ở đây đều là tiêu chí lọc.
DEFAULT_FILTER_PRESETS = {
    "Kỹ sư MEP": {
        "must": {
            "min_exp": 1.0,
            "max_salary": 20.0,
            "degree": ["Đại học", "Kỹ sư"],
            "major": [],
            "keywords": ["AutoCAD", "Revit"]
        },
        "plus": {
            "schools": ["Bách Khoa", "Xây Dựng", "Kiến Trúc", "Điện lực", "Công nghiệp"],
            "keywords": ["Tiếng Anh", "Chứng chỉ"]
        }
    },
    "Kiến trúc sư": {
        "must": {
            "min_exp": 1.0,
            "max_salary": 20.0,
            "degree": ["Đại học"],
            "major": ["Kiến trúc"],
            "keywords": ["Revit", "AutoCAD"]
        },
        "plus": {
            "schools": [],
            "keywords": ["3DMax", "Lumion", "Photoshop", "Sketch", "Tiếng Anh"]
        }
    },
    "Kỹ sư kết cấu": {
        "must": {
            "min_exp": 2.0,
            "max_salary": 20.0,
            "degree": ["Đại học", "Kỹ sư"],
            "major": [],
            "keywords": ["Revit", "AutoCAD"]
        },
        "plus": {
            "schools": ["Xây dựng", "Kiến trúc", "Giao thông vận tải"],
            "keywords": ["Etabs", "Safe", "Microsoft Office", "Tiếng Anh"]
        }
    }
}

# --- CÁC HÀM GET ---
def get_service_account_info(): return SERVICE_ACCOUNT_INFO
def get_spreadsheet_id(): return SPREADSHEET_ID
def get_sheet_name(): return SHEET_NAME
def get_rejected_sheet_name(): return SHEET_NAME_REJECTED

def get_landingai_api_key():
    from settings_manager import SettingsManager
    settings_mgr = SettingsManager()
    return settings_mgr.get("ade_api_key", "")

def get_schema_definition():
    from settings_manager import SettingsManager
    settings_mgr = SettingsManager()
    schema = settings_mgr.get("schema_definition", DEFAULT_SCHEMA_DEFINITION)
    if not schema or not isinstance(schema, list): return DEFAULT_SCHEMA_DEFINITION
    return schema

def get_default_filters(): return DEFAULT_FILTER_PRESETS
def get_schema_keys(): return [item.get("key") for item in get_schema_definition()]
def get_schema_titles(): return [item.get("title") for item in get_schema_definition()]
def get_schema_headers(): return get_schema_titles()