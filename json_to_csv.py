# json_to_csv.py
import csv

def build_data_for_sheet(extracted_list, user_email, schema_definition: list):
    """
    Chuyển dữ liệu thành list.
    Chỉ trả về dữ liệu nội dung (Họ tên, Email...). KHÔNG thêm cột rỗng hay STT.
    """
    data_rows = []
    
    # 1. Header
    headers = []
    field_keys_in_order = []
    
    for field in schema_definition:
        headers.append(field.get("title", ""))
        field_keys_in_order.append(field.get("key", ""))
        
    # 2. Dữ liệu
    for item in extracted_list:
        row_data = []
        for key in field_keys_in_order:
            val = item.get(key, "")
            row_data.append(str(val))
        
        data_rows.append(row_data)
            
    return (headers, data_rows)

# Hàm save_data_to_csv giữ nguyên...
def save_data_to_csv(headers, data_rows, out_path):
    try:
        with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(data_rows)
        return out_path
    except Exception as e:
        print(f"Lỗi lưu CSV: {e}")
        return None