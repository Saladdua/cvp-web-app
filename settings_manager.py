# settings_manager.py
import json
import os
import config 

SETTINGS_FILE = "app_settings.json"

class SettingsManager:
    """Manages persistent user settings."""
    
    DEFAULT_SETTINGS = {
        "credentials_file": "",
        "ade_api_key": "",
        "spreadsheet_id": "",
        "sheet_name": "",
        "user_email": "",
        "schema_definition": config.DEFAULT_SCHEMA_DEFINITION,
        "custom_filters": config.DEFAULT_FILTER_PRESETS # [QUAN TRỌNG] Mặc định lấy từ config
    }
    
    def __init__(self, settings_file=SETTINGS_FILE):
        self.settings_file = settings_file
        self.settings = self.load_settings()
    
    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    defaults = self.DEFAULT_SETTINGS.copy()
                    defaults.update(loaded)
                    
                    # [SỬA LỖI] Nếu custom_filters rỗng -> Lấy lại mặc định
                    if not defaults.get("custom_filters"):
                        defaults["custom_filters"] = config.DEFAULT_FILTER_PRESETS
                        
                    # Kiểm tra Schema
                    if not defaults.get("schema_definition"):
                        defaults["schema_definition"] = config.DEFAULT_SCHEMA_DEFINITION
                        
                    return defaults
            except Exception as e:
                print(f"Error loading settings: {e}")
                return self.DEFAULT_SETTINGS.copy()
        return self.DEFAULT_SETTINGS.copy()
    
    def save_settings(self):
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            return False
    
    def update(self, key, value):
        self.settings[key] = value
        
    def get(self, key, default=None):
        return self.settings.get(key, default)
        
    def is_configured(self):
        return True # Hardcode mode

    def export_shareable_config(self, file_path):
        data = {
            "schema_definition": self.settings.get("schema_definition"),
            "custom_filters": self.settings.get("custom_filters")
        }
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True, "Xuất thành công!"
        except Exception as e: return False, str(e)

    def import_shareable_config(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "custom_filters" in data:
                self.settings["custom_filters"].update(data["custom_filters"])
            if "schema_definition" in data:
                self.settings["schema_definition"] = data["schema_definition"]
                
            self.save_settings()
            return True, "Nhập thành công!"
        except Exception as e: return False, str(e)