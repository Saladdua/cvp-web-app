# google_sheets.py
import os
import json
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import get_service_account_info

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_service_creds():
    try:
        info = get_service_account_info()
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=SCOPES
        )
        return creds
    except Exception as e:
        raise Exception(f"Lỗi xác thực Service Account: {e}")

def get_next_empty_row(service, spreadsheet_id, sheet_name):
    """
    Đếm số dòng có dữ liệu dựa trên cột B (Họ tên).
    Trả về index của dòng trống tiếp theo (Bắt đầu từ 1).
    """
    range_name = f"'{sheet_name}'!B:B"
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values', [])
    return len(values) + 1

def append_values_to_sheet(headers: list, data_rows: list, creds, target_sheet_name: str, spreadsheet_id: str):
    """
    Ghi dữ liệu vào Sheet sử dụng phương pháp UPDATE (Ghi đè vào chỗ trống) 
    thay vì APPEND (Chèn dòng) để kiểm soát chính xác vị trí cột.
    """
    try:
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()

        next_row = get_next_empty_row(service, spreadsheet_id, target_sheet_name)

        if next_row == 1:
            print(f"--> Khởi tạo Header cho sheet: {target_sheet_name}")
            
            formula_stt = [['=VSTACK("STT"; ARRAYFORMULA(IF(B2:B<>""; ROW(B2:B)-1; "")))']]
            sheet.values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{target_sheet_name}'!A1",
                valueInputOption="USER_ENTERED",
                body={"values": formula_stt}
            ).execute()

            header_body = {"values": [headers]}
            sheet.values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{target_sheet_name}'!B1", 
                valueInputOption="USER_ENTERED",
                body=header_body
            ).execute()
            
            next_row = 2
        
        if data_rows:
            target_range = f"'{target_sheet_name}'!B{next_row}"
            body = {"values": data_rows}
            res = sheet.values().update(
                spreadsheetId=spreadsheet_id,
                range=target_range,
                valueInputOption="USER_ENTERED",
                body=body
            ).execute()
            
            return res
        else:
            return {}

    except Exception as e:
        print(f"Google Sheets API Error: {e}")
        raise e

# ==========================================
# CÁC HÀM MỚI CHO TAB QUẢN LÝ (EDIT TRỰC TIẾP)
# ==========================================

def get_sheet_as_dataframe(creds, spreadsheet_id, sheet_name):
    """Đọc toàn bộ Sheet và trả về pandas DataFrame"""
    try:
        service = build("sheets", "v4", credentials=creds)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, 
            range=f"'{sheet_name}'!A1:Z"
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            return pd.DataFrame()
            
        headers = values[0]
        data = values[1:]
        
        df = pd.DataFrame(data, columns=headers)
        return df
        
    except Exception as e:
        raise Exception(f"Lỗi đọc Google Sheet: {e}")

def update_sheet_from_dataframe(creds, spreadsheet_id, sheet_name, df):
    """Xóa dữ liệu cũ và ghi đè DataFrame mới lên Sheet"""
    try:
        service = build("sheets", "v4", credentials=creds)
        
        # Chuyển DataFrame thành list of lists (Bao gồm cả Header)
        data = [df.columns.tolist()] + df.values.tolist()
        
        # 1. Xóa trắng dữ liệu cũ để tránh chồng lấn
        service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A1:Z"
        ).execute()
        
        # 2. Ghi dữ liệu mới vào
        body = {"values": data}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A1",
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        
        return True
    except Exception as e:
        raise Exception(f"Lỗi cập nhật Google Sheet: {e}")