# ade_extractor.py
import json
import ssl
import requests
import os
import tempfile
from pypdf import PdfReader, PdfWriter
from requests.adapters import HTTPAdapter
from datetime import datetime
from config import (
    get_landingai_api_key, 
    ADE_PARSE_ENDPOINT, 
    get_schema_definition,
    MAX_PAGES_TO_SCAN,
    CRITICAL_FIELDS
)

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        kwargs["ssl_context"] = ctx
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)

_session = requests.Session()
_session.mount("https://", TLSAdapter())

def _post_process_data(data):
    # 1. Xử lý Số điện thoại
    phone = data.get("phone", "")
    if phone:
        phone = str(phone).strip()
        phone = re.sub(r"[^0-9+]", "", phone)
        if phone.startswith("+84"): phone = "0" + phone[3:]
        elif phone.startswith("84") and len(phone) > 9: phone = "0" + phone[2:]
        elif phone.startswith("+84-") and len(phone) > 9: phone = "0" + phone[2:]
        elif phone.startswith("84-") and len(phone) > 9: phone = "0" + phone[2:]
        data["phone"] = phone

    # 2. Xử lý Ngày sinh & Tính Tuổi
    dob = data.get("date_of_birth", "")
    age = ""
    if dob:
        dob = str(dob).strip()
        # Lấy năm hiện tại thực tế từ hệ thống
        current_year = datetime.now().year 
        
        birth_year = 0
        # Tìm năm sinh (4 số) trong chuỗi (19xx hoặc 20xx)
        year_match = re.search(r"\b(19|20)\d{2}\b", dob)
        
        if year_match:
            birth_year = int(year_match.group(0))
            # Tính tuổi đơn giản = Năm nay - Năm sinh
            age = current_year - birth_year
        
        # Chuẩn hóa về dd/mm/yyyy
        if "-" in dob and birth_year > 0:
            try:
                parts = re.split(r"[-/]", dob)
                if len(parts) == 3:
                    if len(parts[0]) == 4: # YYYY-MM-DD
                        dob = f"{parts[2]}/{parts[1]}/{parts[0]}"
            except: pass
            
        data["date_of_birth"] = dob
        # Ghi đè tuổi (kể cả AI có đoán sai thì ta cũng tính lại cho đúng)
        data["age"] = age 

    return data

def build_fields_schema():
    try:
        props = {}
        schema_def = get_schema_definition() 
        for field in schema_def:
            t_key = field.get("title")
            if t_key:
                props[t_key] = {"type": ["string", "number", "integer", "null"], "description": field.get("description", "")}
        return {"type": "object", "properties": props}
    except: return {"type": "object", "properties": {}}

def _sanitize_pdf_header(file_path):
    """
    [FIX LỖI QUAN TRỌNG] Tìm và xóa ký tự rác trước %PDF-
    Giúp pypdf đọc được các file bị lỗi header.
    """
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Tìm header chuẩn của PDF
        start_idx = content.find(b'%PDF-')
        
        # Nếu tìm thấy và không phải ở vị trí 0 (tức là có rác ở đầu)
        if start_idx > 0:
            fd, temp_path = tempfile.mkstemp(suffix="_fixed.pdf")
            os.close(fd)
            with open(temp_path, 'wb') as f:
                f.write(content[start_idx:])
            return temp_path, True # Trả về file đã sửa
            
        return file_path, False # File ngon, dùng luôn
    except:
        return file_path, False

def _create_trimmed_pdf(original_path, max_pages):
    """Cắt file PDF (đã được sanitize)."""
    try:
        # strict=False để dễ tính hơn
        reader = PdfReader(original_path, strict=False)
        if reader.is_encrypted: return None, 0
        
        total_pages = len(reader.pages)
        if total_pages <= max_pages: return None, total_pages

        writer = PdfWriter()
        for i in range(max_pages):
            writer.add_page(reader.pages[i])
            
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        
        with open(temp_path, "wb") as f:
            writer.write(f)
            
        return temp_path, max_pages
    except Exception as e:
        return None, 0

def _send_request(file_path, api_key, timeout):
    headers = {"Authorization": f"Bearer {api_key}"}
    fields_schema = build_fields_schema()
    
    file_ext = os.path.splitext(file_path)[1].lower()
    f_key = "pdf" if file_ext == ".pdf" else "file"

    # QUAY VỀ CÁCH GỬI CŨ (ĐƠN GIẢN NHẤT) ĐỂ TRÁNH LỖI 422
    with open(file_path, "rb") as f_handle:
        files = {f_key: f_handle}
        data = {"fields_schema": json.dumps(fields_schema, ensure_ascii=False)}
        return _session.post(ADE_PARSE_ENDPOINT, headers=headers, files=files, data=data, timeout=timeout)

def _merge_results(base_result, new_result):
    merged = base_result.copy()
    for k, v in new_result.items():
        if not merged.get(k) and v:
            merged[k] = v
        elif k in ["ky_nang_ky_thuat", "chung_chi", "software_skills", "certifications"] and v and merged.get(k) != v:
             merged[k] = str(merged.get(k, "")) + "; " + str(v)
    return merged

def extract_schema_from_file(file_path: str, log_callback=None, timeout: int = 180):
    def _log(msg, level="info"):
        if log_callback: log_callback(msg, level)
        else: print(msg)

    api_key = get_landingai_api_key()
    if not api_key: raise Exception("Thiếu API Key")

    file_ext = os.path.splitext(file_path)[1].lower()
    
    # === QUY TRÌNH XỬ LÝ ===
    # 1. Sanitize (Sửa lỗi Header)
    # 2. Cắt trang (Tiết kiệm tiền)
    # 3. Gửi file (Ưu tiên file cắt -> File sửa lỗi -> File gốc)
    
    clean_path = file_path
    is_clean_temp = False
    
    if file_ext == ".pdf":
        clean_path, is_clean_temp = _sanitize_pdf_header(file_path)
        if is_clean_temp:
             _log("--> Đã sửa lỗi Header PDF.", "info")

    # Thử cắt file từ file sạch
    current_path = clean_path
    is_trimmed_temp = False
    
    if file_ext == ".pdf":
        trimmed_path, _ = _create_trimmed_pdf(clean_path, MAX_PAGES_TO_SCAN)
        if trimmed_path:
            current_path = trimmed_path
            is_trimmed_temp = True
    
    try:
        msg_type = " (First 3 pages)" if is_trimmed_temp else ""
        _log(f"--> Scanning{msg_type}...", "info")
        
        resp = _send_request(current_path, api_key, timeout)
        
        # Nếu file cắt bị lỗi 422, thử lại ngay bằng file sạch (full trang)
        if resp.status_code == 422 and is_trimmed_temp:
            _log("--> File cắt bị lỗi. Thử lại bằng file đầy đủ...", "warning")
            if is_trimmed_temp:
                try: os.remove(current_path)
                except: pass
            
            is_trimmed_temp = False
            current_path = clean_path
            resp = _send_request(current_path, api_key, timeout)

        if resp.status_code != 200:
             raise Exception(f"API Error {resp.status_code}: {resp.text}")

        final_result = _process_json(resp.json())
        
        # Dọn dẹp
        if is_trimmed_temp:
            try: os.remove(current_path)
            except: pass

        # Logic quét tiếp trang 2 (nếu cần thiết) có thể thêm ở đây...
        
        return final_result

    except Exception as e:
        if is_trimmed_temp:
            try: os.remove(current_path)
            except: pass
        raise e
    finally:
        if is_clean_temp:
            try: os.remove(clean_path)
            except: pass

def _process_json(rj):
    candidate = {}
    raw = None
    if isinstance(rj.get("data"), dict):
        raw = rj["data"].get("extracted_schema") or rj["data"].get("extraction")
    if raw is None: raw = rj.get("extraction")

    if isinstance(raw, str):
        try: candidate = json.loads(raw)
        except: candidate = {}
    elif isinstance(raw, dict): candidate = raw
    else: candidate = rj 

    from config import get_schema_definition
    schema_def = get_schema_definition()
    title_to_key = {}
    all_keys = []
    for item in schema_def:
        title_to_key[item['title']] = item['key'] 
        title_to_key[item['key']] = item['key']
        all_keys.append(item['key'])

    normalized = {key: "" for key in all_keys}
    if candidate:
        for k, v in candidate.items():
            norm_key = title_to_key.get(k)
            if norm_key in normalized:
                val = _extract_value(v)
                if norm_key in ["phone", "so_dien_thoai"]:
                    val_clean = val.strip().replace(" ", "").replace("-", "").replace(".", "")
                    if val_clean.startswith("+84"): val = "0" + val_clean[3:]
                    elif val_clean.startswith("84") and len(val_clean) > 9: val = "0" + val_clean[2:]
                    else: val = val_clean
                normalized[norm_key] = val
    return normalized

def _extract_value(v):
    if v is None: return ""
    if isinstance(v, str): return v.strip()
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, dict): return str(v.get("value") or "")
    if isinstance(v, list):
        try: return " ; ".join([_extract_value(x) for x in v])
        except: return json.dumps(v, ensure_ascii=False)
    return str(v)