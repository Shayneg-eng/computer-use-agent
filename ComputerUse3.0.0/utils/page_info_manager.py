import json
import os

BASE_FOLDER = "current_page_information"

class PageInfoManager:
    @staticmethod
    def get_all_buttons():
        """Get all buttons"""
        buttons_file = os.path.join(BASE_FOLDER, "buttons", "_index.json")
        if os.path.exists(buttons_file):
            with open(buttons_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("buttons", [])
        return []
    
    @staticmethod
    def get_button_by_id(btn_id):
        """Get specific button by ID"""
        btn_file = os.path.join(BASE_FOLDER, "buttons", f"{btn_id}.json")
        if os.path.exists(btn_file):
            with open(btn_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    @staticmethod
    def get_all_links():
        """Get all links"""
        links_file = os.path.join(BASE_FOLDER, "links", "_index.json")
        if os.path.exists(links_file):
            with open(links_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("links", [])
        return []
    
    @staticmethod
    def get_link_by_id(link_id):
        """Get specific link by ID"""
        link_file = os.path.join(BASE_FOLDER, "links", f"{link_id}.json")
        if os.path.exists(link_file):
            with open(link_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
    
    @staticmethod
    def find_button_by_text(text_query):
        """Find button by text"""
        buttons = PageInfoManager.get_all_buttons()
        return [btn for btn in buttons if text_query.lower() in btn.get("text", "").lower()]
    
    @staticmethod
    def find_link_by_text(text_query):
        """Find link by text"""
        links = PageInfoManager.get_all_links()
        return [link for link in links if text_query.lower() in link.get("text", "").lower()]
    
    @staticmethod
    def get_page_title():
        """Get page title"""
        metadata_file = os.path.join(BASE_FOLDER, "page_metadata", "metadata.json")
        if os.path.exists(metadata_file):
            with open(metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("title", "Unknown")
        return "Unknown"
    
    @staticmethod
    def get_page_url():
        """Get current page URL"""
        metadata_file = os.path.join(BASE_FOLDER, "page_metadata", "metadata.json")
        if os.path.exists(metadata_file):
            with open(metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("url", "Unknown")
        return "Unknown"
    
    @staticmethod
    def get_all_input_fields():
        """Get all input fields"""
        inputs_file = os.path.join(BASE_FOLDER, "input_fields", "_index.json")
        if os.path.exists(inputs_file):
            with open(inputs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("inputs", [])
        return []
    
    @staticmethod
    def get_page_stats():
        """Get page statistics"""
        master_file = os.path.join(BASE_FOLDER, "_master_index.json")
        if os.path.exists(master_file):
            with open(master_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("summary", {})
        return {}
