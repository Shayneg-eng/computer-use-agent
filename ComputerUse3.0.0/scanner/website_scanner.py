import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime
import base64
import os
import shutil
from pathlib import Path

# CONFIGURATION
START_URL = "https://google.com"

BASE_FOLDER = "current_page_information"
SUBFOLDER_STRUCTURE = {
    "page_metadata": "Page Metadata",
    "buttons": "Clickable buttons",
    "links": "Links and navigation",
    "input_fields": "Text inputs, searches, forms",
    "form_elements": "Dropdowns, textareas, select elements",
    "images": "All images on page",
    "text_blocks": "Text content and paragraphs",
    "headings": "Headings (H1-H6)",
    "interactive_elements_index": "Index of all interactive elements"
}

class WebsiteScanner:
    def __init__(self):
        self.extracted_data = {
            "url": "",
            "timestamp": "",
            "page_metadata": {},
            "buttons": [],
            "links": [],
            "text_blocks": [],
            "input_fields": [],
            "form_elements": [],
            "headings": [],
            "images": [],
            "all_interactive_elements": []
        }
        self.setup_folders()
    
    def setup_folders(self):
        """Create and reset the folder structure"""
        if os.path.exists(BASE_FOLDER):
            shutil.rmtree(BASE_FOLDER)
            print(f"[CLEAR] Cleared old page information")
        
        os.makedirs(BASE_FOLDER, exist_ok=True)
        for subfolder in SUBFOLDER_STRUCTURE.keys():
            folder_path = os.path.join(BASE_FOLDER, subfolder)
            os.makedirs(folder_path, exist_ok=True)
        
        print(f"[INIT] Created organized folder structure")
    
    def save_organized_data(self):
        """Save extracted data into organized subfolders"""
        # Save page metadata
        metadata_file = os.path.join(BASE_FOLDER, "page_metadata", "metadata.json")
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(self.extracted_data["page_metadata"], f, indent=2, ensure_ascii=False)
        
        # Save buttons
        buttons_folder = os.path.join(BASE_FOLDER, "buttons")
        for btn in self.extracted_data["buttons"]:
            btn_file = os.path.join(buttons_folder, f"{btn['id']}.json")
            with open(btn_file, "w", encoding="utf-8") as f:
                json.dump(btn, f, indent=2, ensure_ascii=False)
        
        buttons_index = os.path.join(buttons_folder, "_index.json")
        with open(buttons_index, "w", encoding="utf-8") as f:
            json.dump({
                "total_buttons": len(self.extracted_data["buttons"]),
                "buttons": [{"id": b["id"], "text": b["text"], "selector": b["selector"]} 
                           for b in self.extracted_data["buttons"]]
            }, f, indent=2, ensure_ascii=False)
        
        # Save links
        links_folder = os.path.join(BASE_FOLDER, "links")
        for link in self.extracted_data["links"]:
            link_file = os.path.join(links_folder, f"{link['id']}.json")
            with open(link_file, "w", encoding="utf-8") as f:
                json.dump(link, f, indent=2, ensure_ascii=False)
        
        links_index = os.path.join(links_folder, "_index.json")
        with open(links_index, "w", encoding="utf-8") as f:
            json.dump({
                "total_links": len(self.extracted_data["links"]),
                "links": [{"id": l["id"], "text": l["text"], "url": l["url"], "selector": l["selector"]} 
                         for l in self.extracted_data["links"]]
            }, f, indent=2, ensure_ascii=False)
        
        # Save input fields
        inputs_folder = os.path.join(BASE_FOLDER, "input_fields")
        for inp in self.extracted_data["input_fields"]:
            inp_file = os.path.join(inputs_folder, f"{inp['id']}.json")
            with open(inp_file, "w", encoding="utf-8") as f:
                json.dump(inp, f, indent=2, ensure_ascii=False)
        
        inputs_index = os.path.join(inputs_folder, "_index.json")
        with open(inputs_index, "w", encoding="utf-8") as f:
            json.dump({
                "total_inputs": len(self.extracted_data["input_fields"]),
                "inputs": [{"id": i["id"], "type": i["type"], "label": i.get("label"), "selector": i["selector"]} 
                          for i in self.extracted_data["input_fields"]]
            }, f, indent=2, ensure_ascii=False)
        
        # Save form elements
        forms_folder = os.path.join(BASE_FOLDER, "form_elements")
        for elem in self.extracted_data["form_elements"]:
            form_file = os.path.join(forms_folder, f"{elem['id']}.json")
            with open(form_file, "w", encoding="utf-8") as f:
                json.dump(elem, f, indent=2, ensure_ascii=False)
        
        forms_index = os.path.join(forms_folder, "_index.json")
        with open(forms_index, "w", encoding="utf-8") as f:
            json.dump({
                "total_form_elements": len(self.extracted_data["form_elements"]),
                "forms": [{"id": e["id"], "type": e["type"], "selector": e["selector"]} 
                         for e in self.extracted_data["form_elements"]]
            }, f, indent=2, ensure_ascii=False)
        
        # Save images
        images_folder = os.path.join(BASE_FOLDER, "images")
        for img in self.extracted_data["images"]:
            img_file = os.path.join(images_folder, f"{img['id']}.json")
            with open(img_file, "w", encoding="utf-8") as f:
                json.dump(img, f, indent=2, ensure_ascii=False)
        
        images_index = os.path.join(images_folder, "_index.json")
        with open(images_index, "w", encoding="utf-8") as f:
            json.dump({
                "total_images": len(self.extracted_data["images"]),
                "images": [{"id": i["id"], "alt": i["alt"], "visible": i["visible"], "selector": i["selector"]} 
                          for i in self.extracted_data["images"]]
            }, f, indent=2, ensure_ascii=False)
        
        # Save text blocks
        text_folder = os.path.join(BASE_FOLDER, "text_blocks")
        for text in self.extracted_data["text_blocks"]:
            text_file = os.path.join(text_folder, f"{text['id']}.json")
            with open(text_file, "w", encoding="utf-8") as f:
                json.dump(text, f, indent=2, ensure_ascii=False)
        
        text_index = os.path.join(text_folder, "_index.json")
        with open(text_index, "w", encoding="utf-8") as f:
            json.dump({
                "total_text_blocks": len(self.extracted_data["text_blocks"]),
                "text_blocks": [{"id": t["id"], "content_preview": t["content"][:100], "selector": t["selector"]} 
                               for t in self.extracted_data["text_blocks"]]
            }, f, indent=2, ensure_ascii=False)
        
        # Save headings
        headings_folder = os.path.join(BASE_FOLDER, "headings")
        for heading in self.extracted_data["headings"]:
            heading_file = os.path.join(headings_folder, f"{heading['id']}.json")
            with open(heading_file, "w", encoding="utf-8") as f:
                json.dump(heading, f, indent=2, ensure_ascii=False)
        
        headings_index = os.path.join(headings_folder, "_index.json")
        with open(headings_index, "w", encoding="utf-8") as f:
            json.dump({
                "total_headings": len(self.extracted_data["headings"]),
                "headings": [{"id": h["id"], "tag": h["tag"], "text": h["text"][:80], "selector": h["selector"]} 
                            for h in self.extracted_data["headings"]]
            }, f, indent=2, ensure_ascii=False)
        
        # Save interactive elements index
        interactive_file = os.path.join(BASE_FOLDER, "interactive_elements_index", "all_elements.json")
        with open(interactive_file, "w", encoding="utf-8") as f:
            json.dump({
                "total_interactive_elements": len(self.extracted_data["all_interactive_elements"]),
                "timestamp": self.extracted_data["timestamp"],
                "url": self.extracted_data["url"],
                "elements": self.extracted_data["all_interactive_elements"]
            }, f, indent=2, ensure_ascii=False)
        
        # Create master index
        master_index_path = os.path.join(BASE_FOLDER, "_master_index.json")
        with open(master_index_path, "w", encoding="utf-8") as f:
            json.dump({
                "page_url": self.extracted_data["url"],
                "timestamp": self.extracted_data["timestamp"],
                "title": self.extracted_data["page_metadata"].get("title", "Unknown"),
                "summary": {
                    "total_buttons": len(self.extracted_data["buttons"]),
                    "total_links": len(self.extracted_data["links"]),
                    "total_input_fields": len(self.extracted_data["input_fields"]),
                    "total_form_elements": len(self.extracted_data["form_elements"]),
                    "total_images": len(self.extracted_data["images"]),
                    "total_headings": len(self.extracted_data["headings"]),
                    "total_text_blocks": len(self.extracted_data["text_blocks"]),
                    "total_interactive_elements": len(self.extracted_data["all_interactive_elements"])
                }
            }, f, indent=2, ensure_ascii=False)
    
    async def extract_page_metadata(self, page):
        """Extract page-level metadata"""
        metadata = await page.evaluate("""() => {
            return {
                title: document.title,
                url: window.location.href,
                viewport: {
                    width: window.innerWidth,
                    height: window.innerHeight
                },
                pathname: window.location.pathname,
                hostname: window.location.hostname,
                description: document.querySelector('meta[name="description"]')?.getAttribute('content'),
                language: document.documentElement.lang
            };
        }""")
        return metadata
    
    async def scan_website(self, url):
        """Scan a website and extract all relevant information"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            print(f"\n[SCAN] Opening URL: {url}")
            try:
                await page.goto(url, wait_until="load", timeout=15000)
            except Exception as e:
                print(f"[WARN] Load timeout, proceeding anyway...")
            
            # Extra wait for dynamic content, especially important for Google and similar sites
            await asyncio.sleep(2)
            
            # Try to wait for networkidle as well (gives JS time to finish)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except:
                pass
            
            self.extracted_data["url"] = url
            self.extracted_data["timestamp"] = datetime.now().isoformat()
            self.extracted_data["page_metadata"] = await self.extract_page_metadata(page)
            
            # Extract all elements
            await asyncio.gather(
                self.extract_headings(page),
                self.extract_text_blocks(page),
                self.extract_buttons(page),
                self.extract_links(page),
                self.extract_input_fields(page),
                self.extract_images(page),
                self.extract_form_elements(page)
            )
            
            self.save_organized_data()
            print(f"[OK] Scan complete: {len(self.extracted_data['buttons'])} buttons, {len(self.extracted_data['links'])} links, {len(self.extracted_data['input_fields'])} inputs found")
            
            await browser.close()
    
    # Helper methods
    async def get_element_selector(self, element):
        try:
            selector = await element.evaluate("""(el) => {
                if (el.id) return '#' + el.id;
                const path = [];
                let current = el;
                while (current && current !== document.body) {
                    let index = 1;
                    let sibling = current.previousElementSibling;
                    while (sibling) {
                        if (sibling.tagName === current.tagName) index++;
                        sibling = sibling.previousElementSibling;
                    }
                    const tag = current.tagName.toLowerCase();
                    const indexStr = current.parentElement?.children.length > 1 ? `:nth-of-type(${index})` : '';
                    path.unshift(tag + indexStr);
                    current = current.parentElement;
                }
                return path.join(' > ');
            }""")
            return selector
        except:
            return None
    
    async def get_element_bounds(self, element):
        try:
            bounds = await element.evaluate("""(el) => {
                const rect = el.getBoundingClientRect();
                return {
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                };
            }""")
            return bounds
        except:
            return None
    
    async def get_accessibility_info(self, element):
        try:
            acc_info = await element.evaluate("""(el) => {
                return {
                    ariaLabel: el.getAttribute('aria-label'),
                    role: el.getAttribute('role'),
                    title: el.getAttribute('title')
                };
            }""")
            return {k: v for k, v in acc_info.items() if v}
        except:
            return {}
    
    async def get_all_attributes(self, element):
        try:
            attrs = await element.evaluate("""(el) => {
                const attrs = {};
                for (let attr of el.attributes) {
                    attrs[attr.name] = attr.value;
                }
                return attrs;
            }""")
            return attrs
        except:
            return {}
    
    async def get_parent_info(self, element):
        try:
            parent_info = await element.evaluate("""(el) => {
                if (!el.parentElement) return null;
                const parent = el.parentElement;
                return {
                    tag: parent.tagName.toLowerCase(),
                    id: parent.id || null,
                    class: parent.className || null
                };
            }""")
            return parent_info
        except:
            return None
    
    async def get_form_context(self, element):
        try:
            form_info = await element.evaluate("""(el) => {
                const form = el.closest('form');
                if (!form) return null;
                return {
                    formAction: form.getAttribute('action'),
                    formMethod: form.getAttribute('method')
                };
            }""")
            return form_info
        except:
            return None
    
    async def get_label_for_input(self, element):
        try:
            label_text = await element.evaluate("""(el) => {
                if (el.id) {
                    const label = document.querySelector(`label[for="${el.id}"]`);
                    if (label) return label.textContent;
                }
                const parentLabel = el.closest('label');
                if (parentLabel) return parentLabel.textContent;
                if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
                if (el.placeholder) return el.placeholder;
                return null;
            }""")
            return label_text
        except:
            return None
    
    async def extract_headings(self, page):
        headings = await page.query_selector_all("h1, h2, h3, h4, h5, h6")
        for idx, heading in enumerate(headings):
            text = await heading.text_content()
            if text and text.strip():
                tag = await heading.evaluate("el => el.tagName")
                self.extracted_data["headings"].append({
                    "id": f"heading_{idx}",
                    "tag": tag,
                    "text": text.strip(),
                    "visible": await heading.is_visible(),
                    "selector": await self.get_element_selector(heading),
                    "bounds": await self.get_element_bounds(heading)
                })
    
    async def extract_text_blocks(self, page):
        paragraphs = await page.query_selector_all("p, main, article, section > div")
        for idx, element in enumerate(paragraphs):
            text = await element.text_content()
            if text and text.strip() and len(text.strip()) > 10:
                self.extracted_data["text_blocks"].append({
                    "id": f"text_{idx}",
                    "content": text.strip()[:500],
                    "visible": await element.is_visible(),
                    "selector": await self.get_element_selector(element)
                })
    
    async def extract_buttons(self, page):
        buttons = await page.query_selector_all("button, input[type='button'], input[type='submit'], input[type='reset']")
        for idx, button in enumerate(buttons):
            text = await button.text_content()
            button_type = await button.get_attribute("type")
            visible = await button.is_visible()
            
            button_label = text.strip() if text and text.strip() else f"Button {idx}"
            is_submit = button_type == "submit" or await button.evaluate("el => el.form !== null")
            action = "submit" if is_submit else "click"
            
            button_data = {
                "id": f"btn_{idx}",
                "text": button_label,
                "visible": visible,
                "clickable": await button.is_enabled(),
                "action": action,
                "selector": await self.get_element_selector(button),
                "bounds": await self.get_element_bounds(button)
            }
            self.extracted_data["buttons"].append(button_data)
            self.extracted_data["all_interactive_elements"].append({
                "type": "BUTTON",
                "id": f"btn_{idx}",
                "label": button_label,
                "action": action
            })
    
    async def extract_links(self, page):
        links = await page.query_selector_all("a")
        for idx, link in enumerate(links):
            text = await link.text_content()
            href = await link.get_attribute("href")
            visible = await link.is_visible()
            
            if text and text.strip() and href:
                link_data = {
                    "id": f"link_{idx}",
                    "text": text.strip(),
                    "url": href,
                    "visible": visible,
                    "selector": await self.get_element_selector(link),
                    "bounds": await self.get_element_bounds(link)
                }
                self.extracted_data["links"].append(link_data)
                self.extracted_data["all_interactive_elements"].append({
                    "type": "LINK",
                    "id": f"link_{idx}",
                    "label": text.strip()[:100],
                    "url": href
                })
    
    async def extract_input_fields(self, page):
        # Try multiple selector strategies to find inputs
        input_selectors = [
            "input:not([type='hidden']):not([type='button']):not([type='submit']):not([type='reset'])",
            "input[type='text']",
            "input[type='search']",
            "input:not([type])",  # inputs without explicit type
            "textarea"
        ]
        
        found_inputs = set()  # Track by selector to avoid duplicates
        
        for selector in input_selectors:
            try:
                inputs = await page.query_selector_all(selector)
                for idx, inp in enumerate(inputs):
                    # Get unique identifier to avoid duplicates
                    sel = await self.get_element_selector(inp)
                    if sel in found_inputs:
                        continue
                    found_inputs.add(sel)
                    
                    input_type = await inp.get_attribute("type")
                    visible = await inp.is_visible()
                    placeholder = await inp.get_attribute("placeholder")
                    label_text = await self.get_label_for_input(inp)
                    name = await inp.get_attribute("name")
                    
                    input_data = {
                        "id": f"input_{len(self.extracted_data['input_fields'])}",
                        "type": input_type or "text",
                        "placeholder": placeholder or "",
                        "label": label_text,
                        "name": name or "",
                        "visible": visible,
                        "selector": sel,
                        "bounds": await self.get_element_bounds(inp)
                    }
                    self.extracted_data["input_fields"].append(input_data)
                    self.extracted_data["all_interactive_elements"].append({
                        "type": "INPUT",
                        "id": input_data["id"],
                        "label": label_text or placeholder or name or f"Input_{len(self.extracted_data['input_fields'])-1}",
                        "input_type": input_type or "text"
                    })
            except:
                pass  # Selector didn't work, try next one
    
    async def extract_images(self, page):
        images = await page.query_selector_all("img")
        for idx, img in enumerate(images):
            src = await img.get_attribute("src")
            alt = await img.get_attribute("alt")
            visible = await img.is_visible()
            
            if src:
                self.extracted_data["images"].append({
                    "id": f"img_{idx}",
                    "src": src,
                    "alt": alt or "No description",
                    "visible": visible,
                    "selector": await self.get_element_selector(img),
                    "bounds": await self.get_element_bounds(img)
                })
    
    async def extract_form_elements(self, page):
        selects = await page.query_selector_all("select, textarea")
        for idx, element in enumerate(selects):
            tag = await element.evaluate("el => el.tagName")
            visible = await element.is_visible()
            label_text = await self.get_label_for_input(element)
            
            options = []
            if tag.upper() == "SELECT":
                option_elements = await element.query_selector_all("option")
                for opt_idx, opt in enumerate(option_elements):
                    opt_text = await opt.text_content()
                    opt_value = await opt.get_attribute("value")
                    options.append({
                        "index": opt_idx,
                        "text": opt_text.strip() if opt_text else "",
                        "value": opt_value or ""
                    })
            
            form_elem_data = {
                "id": f"form_{idx}",
                "type": tag,
                "visible": visible,
                "label": label_text,
                "options": options if tag.upper() == "SELECT" else None,
                "selector": await self.get_element_selector(element),
                "bounds": await self.get_element_bounds(element)
            }
            self.extracted_data["form_elements"].append(form_elem_data)
            self.extracted_data["all_interactive_elements"].append({
                "type": f"FORM_{tag}",
                "id": f"form_{idx}",
                "label": label_text or f"{tag} element"
            })


async def main():
    scanner = WebsiteScanner()
    await scanner.scan_website(START_URL)


if __name__ == "__main__":
    asyncio.run(main())
