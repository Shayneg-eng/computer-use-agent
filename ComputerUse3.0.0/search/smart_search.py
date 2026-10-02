import json
import os
from pathlib import Path

BASE_FOLDER = "current_page_information"

class SmartSearch:
    @staticmethod
    def search_buttons(query, limit=5):
        """Search for buttons by text"""
        buttons = []
        buttons_folder = os.path.join(BASE_FOLDER, "buttons")
        
        if not os.path.exists(buttons_folder):
            return []
        
        # Load index first
        index_path = os.path.join(buttons_folder, "_index.json")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
                for btn in index["buttons"]:
                    if query.lower() in btn["text"].lower():
                        buttons.append(btn)
        
        return buttons[:limit]
    
    @staticmethod
    def search_links(query, limit=5):
        """Search for links by text or URL"""
        links = []
        links_folder = os.path.join(BASE_FOLDER, "links")
        
        if not os.path.exists(links_folder):
            return []
        
        # Load index first
        index_path = os.path.join(links_folder, "_index.json")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
                for link in index["links"]:
                    if query.lower() in link["text"].lower() or query.lower() in link["url"].lower():
                        links.append(link)
        
        return links[:limit]
    
    @staticmethod
    def search_inputs(query, limit=5):
        """Search for input fields by label or type"""
        inputs = []
        inputs_folder = os.path.join(BASE_FOLDER, "input_fields")
        
        if not os.path.exists(inputs_folder):
            return []
        
        # Load index first
        index_path = os.path.join(inputs_folder, "_index.json")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
                for inp in index["inputs"]:
                    label = inp.get("label", "")
                    if query.lower() in label.lower() or query.lower() in inp["type"].lower():
                        inputs.append(inp)
        
        return inputs[:limit]
    
    @staticmethod
    def search_text(query, limit=5):
        """Search for text content"""
        text_results = []
        text_folder = os.path.join(BASE_FOLDER, "text_blocks")
        
        if not os.path.exists(text_folder):
            return []
        
        # For text blocks, need to check full files since they're summarized in index
        for file in os.listdir(text_folder):
            if file.endswith(".json") and file != "_index.json":
                file_path = os.path.join(text_folder, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        text_obj = json.load(f)
                        if query.lower() in text_obj["content"].lower():
                            text_results.append({
                                "id": text_obj["id"],
                                "content": text_obj["content"][:200],
                                "visible": text_obj.get("visible", True)
                            })
                except:
                    pass
        
        return text_results[:limit]
    
    @staticmethod
    def search_all(query):
        """Search across all categories"""
        results = {
            "buttons": SmartSearch.search_buttons(query, limit=3),
            "links": SmartSearch.search_links(query, limit=3),
            "inputs": SmartSearch.search_inputs(query, limit=3),
            "text": SmartSearch.search_text(query, limit=2)
        }
        return results
    
    @staticmethod
    def get_visible_buttons():
        """Get all visible buttons"""
        buttons = []
        buttons_folder = os.path.join(BASE_FOLDER, "buttons")
        
        if not os.path.exists(buttons_folder):
            return []
        
        index_path = os.path.join(buttons_folder, "_index.json")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
                for btn in index["buttons"]:
                    buttons.append(btn)
        
        return buttons
    
    @staticmethod
    def get_visible_links():
        """Get all visible links"""
        links = []
        links_folder = os.path.join(BASE_FOLDER, "links")
        
        if not os.path.exists(links_folder):
            return []
        
        index_path = os.path.join(links_folder, "_index.json")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                index = json.load(f)
                for link in index["links"]:
                    links.append(link)
        
        return links
    
    @staticmethod
    def get_page_overview():
        """Get overview of page structure"""
        master_index_path = os.path.join(BASE_FOLDER, "_master_index.json")
        
        if not os.path.exists(master_index_path):
            return None
        
        with open(master_index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    @staticmethod
    def get_folder_summary(folder_name):
        """Get summary of a specific folder"""
        folder_path = os.path.join(BASE_FOLDER, folder_name)
        index_path = os.path.join(folder_path, "_index.json")
        
        if not os.path.exists(index_path):
            return None
        
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    @staticmethod
    def get_element_by_id(element_type, element_id):
        """Get specific element by ID and type"""
        folder_map = {
            "button": "buttons",
            "link": "links",
            "input": "input_fields",
            "text": "text_blocks",
            "heading": "headings",
            "image": "images",
            "form": "form_elements"
        }
        
        folder_name = folder_map.get(element_type)
        if not folder_name:
            return None
        
        file_path = os.path.join(BASE_FOLDER, folder_name, f"{element_id}.json")
        
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
