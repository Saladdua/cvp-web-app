# career_api.py
import requests
import re
from bs4 import BeautifulSoup

API_BASE_URL = "https://career.innojsc.com/api"

def get_job_details(job_id, api_key):
    # (Giữ nguyên như cũ)
    url = f"{API_BASE_URL}/jobs/{job_id}"
    headers = {"x-api-key": api_key}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("data", {})
        return None
    except:
        return None

def fetch_all_active_jobs(api_key):
    """
    [MỚI] Lấy danh sách toàn bộ Job đang tuyển.
    """
    url = f"{API_BASE_URL}/jobs"
    headers = {"x-api-key": api_key}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 401:
            return None, "Lỗi 401 (Unauthorized): API Key bị sai."
        elif response.status_code != 200:
            return None, f"Lỗi {response.status_code}: Không lấy được dữ liệu."
            
        json_data = response.json()
        jobs = json_data.get("data", [])
        
        if not jobs:
            return [], "Không có Job nào đang tuyển (danh sách rỗng)."
            
        return jobs, "OK"

    except Exception as e:
        return None, f"Lỗi kết nối: {str(e)}"

def parse_salary_string(salary_str):
    # (Giữ nguyên như cũ)
    if not salary_str: return 0
    numbers = re.findall(r"(\d+)", str(salary_str).replace(".", "").replace(",", ""))
    if numbers:
        return float(max(numbers, key=int)) / 1000000 # Chuyển về đơn vị triệu
    return 0

def convert_jd_to_filter(job_data):
    # (Giữ nguyên như cũ)
    if not job_data: return None

    req_html = job_data.get("requirements", "")
    soup = BeautifulSoup(req_html, "html.parser")
    req_text = soup.get_text().lower()
    
    degree = []
    if "đại học" in req_text: degree.append("Đại học")
    if "cao đẳng" in req_text: degree.append("Cao đẳng")
    
    max_sal = parse_salary_string(job_data.get("salary"))
    keywords = job_data.get("tags", [])
    min_exp = float(job_data.get("experience", 0))

    filter_rule = {
        "name": job_data.get("title"),
        "must": {
            "min_exp": min_exp,
            "max_salary": max_sal,
            "degree": degree,
            "keywords": keywords,
            "major": []
        },
        "plus": {"schools": [], "keywords": []}
    }
    return filter_rule