#!/usr/bin/env python3
"""
Enhanced Computer Use AI - Optimized for accurate button clicking and intelligent HTML processing
"""

import asyncio
import json
import re
import sys
import random
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
import openai
import logging
import os

# Configuration
LLM_CONFIG = {
    "deepseek": {
        "api_key": os.environ["DEEPSEEK_API_KEY"],
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "max_tokens": 8192,
        "temperature": 0.1
    }
}

BROWSER_CONFIG = {
    "headless": False,  # Already set to False - this makes browser visible
    "viewport": {"width": 1280, "height": 720},
    "timeout": 30000,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "ignore_https_errors": True,  # Add this
    "ignore_default_args": ["--enable-automation"]  # Add this
}

SYSTEM_CONFIG = {
    "llm_provider": "deepseek",
    "max_steps": 50,
    "html_truncate_length": 15000,
    "screenshot_on_error": True,
    "log_level": "INFO",
    "human_like_delays": True,
    "min_delay": 2,
    "max_delay": 4
}

DEFAULT_TASK = "make a reservation at an italian restaurant for 8/26/2025 for 4 people in charlotte"
START_URL = "https://www.opentable.com/cuisine/best-italian-restaurants-charlotte-nc"
SUPPORTED_ACTIONS = ["click", "navigate", "type", "scroll", "wait", "none", "ask", "tell"]

class EnhancedLogger:
    """Enhanced logging system"""
    
    def __init__(self, name="computer_use_ai"):
        self.logger = logging.getLogger(name)
        self.setup_logger()
    
    def setup_logger(self):
        if not os.path.exists("logs"):
            os.makedirs("logs")
        
        level = getattr(logging, SYSTEM_CONFIG["log_level"], logging.INFO)
        self.logger.setLevel(level)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        log_filename = f"logs/ai_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_filename)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message):
        self.logger.info(message)
    
    def debug(self, message):
        self.logger.debug(message)
    
    def warning(self, message):
        self.logger.warning(message)
    
    def error(self, message):
        self.logger.error(message)

class SmartHTMLProcessor:
    """Intelligent HTML processor that provides targeted content for LLM"""
    
    def __init__(self):
        self.logger = EnhancedLogger()
        
        # Enhanced element priorities
        self.critical_elements = ['input', 'button', 'select', 'textarea', 'a']
        self.important_elements = ['form', 'label', 'option', 'h1', 'h2', 'h3']
        self.contextual_elements = ['nav', 'main', 'section', 'div', 'span', 'p']
        
        # Patterns for important content
        self.important_patterns = [
            r'\$\d+\.?\d*',  # prices
            r'\d+\.\d+\s*star',  # ratings
            r'\d{1,2}:\d{2}\s*[ap]m',  # times
            r'(available|unavailable|book|reserve)',  # booking status
            r'\d+\s*people?',  # party size
            r'\d{1,2}\/\d{1,2}\/\d{4}',  # dates
            r'(morning|afternoon|evening|tonight)',  # time periods
        ]
        
    def is_relevant_element(self, element):
        """Check if element is relevant for the task"""
        # Skip cookie/consent related elements
        element_str = str(element).lower()
        if any(term in element_str for term in ['cookie', 'consent', 'privacy-policy', 'vendor-search', 'gdpr']):
            return False
        
        # Skip hidden elements
        if element.get('style'):
            style = element.get('style', '').lower()
            if any(term in style for term in ['display: none', 'visibility: hidden', 'opacity: 0']):
                return False
        
        # Skip elements with suspicious IDs
        element_id = element.get('id', '').lower()
        if any(term in element_id for term in ['cookie', 'vendor', 'consent', 'privacy', 'gdpr', 'tracking']):
            return False
        
        # Skip elements with suspicious classes
        element_classes = ' '.join(element.get('class', [])).lower()
        if any(term in element_classes for term in ['cookie', 'vendor', 'consent', 'privacy', 'gdpr', 'tracking']):
            return False
        
        # Skip elements that are likely overlays or modals that aren't the main content
        if element.get('role') in ['dialog', 'alertdialog'] and 'cookie' in element_str:
            return False
        
        return True
    
    def analyze_page_intent(self, soup):
        """Determine the page's primary intent and structure"""
        # Restaurant search/listing page
        if soup.find_all(attrs={"class": re.compile(r"restaurant|listing", re.I)}):
            return "restaurant_listing"
        
        # Reservation/booking page
        if soup.find_all(attrs={"class": re.compile(r"reservation|booking", re.I)}) or \
           soup.find_all("select", attrs={"name": re.compile(r"party|date|time", re.I)}):
            return "reservation_form"
        
        # Search results page
        if soup.find(text=re.compile(r"\d+\s*results?", re.I)) or \
           soup.find_all(attrs={"class": re.compile(r"search.*result", re.I)}):
            return "search_results"
        
        # General form page
        if len(soup.find_all("form")) > 0:
            return "form_page"
        
        return "general"
    
    def extract_smart_selectors(self, element):
        """Generate multiple high-reliability selectors for an element"""
        selectors = []
        
        # Skip hidden elements or cookie-related elements
        if element.get('style') and any(hide_term in element.get('style', '') for hide_term in ['display: none', 'visibility: hidden']):
            return []
        
        # Skip cookie/consent/vendor related elements
        element_str = str(element).lower()
        element_id = element.get('id', '').lower()
        element_classes = ' '.join(element.get('class', [])).lower()
        
        if any(term in element_str for term in ['cookie', 'consent', 'privacy-policy', 'vendor-search']):
            return []
        if any(term in element_id for term in ['cookie', 'vendor', 'consent', 'privacy']):
            return []
        if any(term in element_classes for term in ['cookie', 'vendor', 'consent', 'privacy']):
            return []
        
        # ID selector (highest priority)
        if element.get('id'):
            selectors.append({
                'selector': f"#{element['id']}",
                'reliability': 95,
                'type': 'id'
            })
        
        # Name + type combination (very reliable for forms)
        if element.get('name'):
            base_selector = f"[name='{element['name']}']"
            if element.get('type'):
                base_selector = f"{element.name}[name='{element['name']}'][type='{element['type']}']"
            selectors.append({
                'selector': base_selector,
                'reliability': 90,
                'type': 'name_type'
            })
        
        # Data attributes (usually stable) - but skip tracking/analytics ones
        for attr in element.attrs:
            if attr.startswith('data-') and attr not in ['data-reactid', 'data-tracking', 'data-analytics']:
                value = element[attr]
                if isinstance(value, list):
                    value = ' '.join(value)
                # Skip if it looks like dynamic/generated data
                if not re.match(r'^[a-zA-Z0-9_-]+$', str(value)):
                    continue
                selectors.append({
                    'selector': f"[{attr}='{value}']",
                    'reliability': 80,
                    'type': 'data_attr'
                })
        
        # Aria labels (semantic and stable)
        if element.get('aria-label') and len(element.get('aria-label', '')) > 2:
            selectors.append({
                'selector': f"[aria-label='{element['aria-label']}']",
                'reliability': 85,
                'type': 'aria'
            })
        
        # Role-based selectors
        if element.get('role'):
            selectors.append({
                'selector': f"[role='{element['role']}']",
                'reliability': 75,
                'type': 'role'
            })
        
        # Placeholder text (good for inputs)
        if element.get('placeholder') and len(element.get('placeholder', '')) > 2:
            selectors.append({
                'selector': f"[placeholder='{element['placeholder']}']",
                'reliability': 80,
                'type': 'placeholder'
            })
        
        # Class-based (filter for stable classes)
        classes = element.get('class', [])
        stable_classes = [cls for cls in classes 
                        if len(cls) > 3 
                        and not re.match(r'^[a-zA-Z]{1,3}\d+', cls)  # Skip generated classes
                        and not any(term in cls.lower() for term in ['cookie', 'vendor', 'tracking'])]
        if stable_classes:
            # Use just first stable class to avoid over-specificity
            selectors.append({
                'selector': f"{element.name}.{stable_classes[0]}",
                'reliability': 60,
                'type': 'class'
            })
        
        # For input elements, add type-specific selectors
        if element.name == 'input' and element.get('type'):
            input_type = element.get('type')
            if input_type in ['search', 'text', 'email', 'tel']:
                selectors.append({
                    'selector': f"input[type='{input_type}']:visible",
                    'reliability': 70,
                    'type': 'input_type'
                })
        
        # Sort by reliability and return top 3
        selectors.sort(key=lambda x: x['reliability'], reverse=True)
        return selectors[:3]
    
    def extract_element_context(self, element):
        """Extract rich context about an element's purpose and state"""
        context = {}
        
        # Get associated label
        label_text = self.find_element_label(element)
        if label_text:
            context['label'] = label_text
        
        # Get nearby descriptive text
        nearby_text = self.get_nearby_text(element, max_distance=2)
        if nearby_text:
            context['nearby_text'] = nearby_text[:100]  # Truncate long text
        
        # Determine element purpose from patterns
        element_text = element.get_text(strip=True) if hasattr(element, 'get_text') else ''
        combined_text = f"{label_text} {nearby_text} {element_text}".lower()
        
        # Purpose detection
        if any(word in combined_text for word in ['submit', 'search', 'find', 'go']):
            context['purpose'] = 'submit_action'
        elif any(word in combined_text for word in ['date', 'calendar', 'when']):
            context['purpose'] = 'date_selection'
        elif any(word in combined_text for word in ['time', 'hour', 'minute']):
            context['purpose'] = 'time_selection'
        elif any(word in combined_text for word in ['party', 'people', 'guest', 'size']):
            context['purpose'] = 'party_size'
        elif any(word in combined_text for word in ['book', 'reserve', 'table']):
            context['purpose'] = 'booking_action'
        
        # Current state (for form elements)
        if element.name in ['select', 'input', 'textarea']:
            if element.name == 'select':
                selected_option = element.find('option', selected=True)
                context['current_value'] = selected_option.get_text(strip=True) if selected_option else 'None selected'
            elif element.name == 'input':
                context['current_value'] = element.get('value', '')
                context['placeholder'] = element.get('placeholder', '')
        
        return context
    
    def find_element_label(self, element):
        """Find associated label text using multiple strategies"""
        # Strategy 1: explicit label with 'for' attribute
        if element.get('id'):
            label = element.find_parent().find('label', attrs={'for': element['id']})
            if label:
                return label.get_text(strip=True)
        
        # Strategy 2: parent label
        parent_label = element.find_parent('label')
        if parent_label:
            label_text = parent_label.get_text(strip=True)
            element_text = element.get_text(strip=True) if hasattr(element, 'get_text') else ''
            return label_text.replace(element_text, '').strip()
        
        # Strategy 3: aria-label or title
        return element.get('aria-label') or element.get('title') or element.get('placeholder', '')
    
    def get_nearby_text(self, element, max_distance=3):
        """Get descriptive text near the element"""
        nearby_texts = []
        
        # Check siblings
        for sibling in element.find_previous_siblings():
            if hasattr(sibling, 'get_text'):
                text = sibling.get_text(strip=True)
                if text and len(text) < 200:
                    nearby_texts.append(text)
                    break
        
        # Check parent's text
        parent = element.parent
        depth = 0
        while parent and depth < max_distance:
            parent_text = parent.get_text(strip=True) if hasattr(parent, 'get_text') else ''
            if parent_text:
                # Remove nested element text to get just the parent's text
                for child in parent.find_all():
                    if hasattr(child, 'get_text'):
                        parent_text = parent_text.replace(child.get_text(strip=True), '')
                parent_text = parent_text.strip()
                if parent_text and len(parent_text) < 100:
                    nearby_texts.append(parent_text)
                    break
            parent = parent.parent
            depth += 1
        
        return ' '.join(nearby_texts)
    
    def prioritize_content(self, soup, page_intent):
        """Prioritize content based on page intent and task relevance"""
        prioritized_elements = []
        
        # Remove cookie banners and hidden elements first
        for element in soup.find_all(['div', 'section', 'aside'], attrs={'class': re.compile(r'cookie|consent|privacy|gdpr', re.I)}):
            element.decompose()
        for element in soup.find_all(attrs={'id': re.compile(r'cookie|consent|privacy|gdpr|vendor-search', re.I)}):
            element.decompose()
        
        if page_intent == "restaurant_listing":
            # More specific selectors for OpenTable and restaurant sites
            priority_selectors = [
                # Main search functionality
                'input[placeholder*="restaurant" i]:not([id*="cookie"]):not([id*="vendor"])',
                'input[placeholder*="location" i]:not([id*="cookie"]):not([id*="vendor"])', 
                'input[data-testid*="search"]:not([id*="cookie"])',
                'input[data-testid*="typeahead"]:not([id*="cookie"])',
                'button[class*="search" i]:not([class*="cookie"])',
                
                # Booking related elements
                'button[class*="book"], button[class*="reserve"]',
                'a[href*="/restaurant/"], a[href*="/r/"]',
                'select[name*="party"], select[name*="size"], select[name*="guest"]',
                'input[name*="date"], input[type="date"]',
                'select[name*="time"], input[type="time"]',
                
                # Restaurant cards and listings
                'div[class*="restaurant"]:not([class*="cookie"]), div[class*="listing"]:not([class*="cookie"])',
                'article[class*="restaurant"], section[class*="restaurant"]'
            ]
        elif page_intent == "reservation_form":
            # Prioritize form elements, especially date/time/party size
            priority_selectors = [
                'select[name*="party"], select[name*="size"], select[name*="guest"]',
                'select[name*="date"], input[type="date"], input[name*="date"]',
                'select[name*="time"], input[type="time"], input[name*="time"]',
                'button[type="submit"]:not([class*="cookie"]), input[type="submit"]:not([class*="cookie"])',
                'button[class*="book"], button[class*="reserve"], button[class*="confirm"]',
                'form:not([class*="cookie"]):not([id*="cookie"])'
            ]
        else:
            # General prioritization with cookie filtering
            priority_selectors = [
                'button:not([id*="cookie"]):not([class*="cookie"])', 
                'input[type="submit"]:not([id*="cookie"])', 
                'a[href]:not([href*="cookie"]):not([href*="privacy"])',
                'select:not([id*="cookie"])', 
                'input[type="text"]:not([id*="cookie"]):not([id*="vendor"])', 
                'input[type="search"]:not([id*="cookie"]):not([id*="vendor"])',
                'form:not([id*="cookie"]):not([class*="cookie"])'
            ]
        
        # Extract prioritized elements with relevance filtering
        for selector in priority_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    # Apply relevance filter
                    if not self.is_relevant_element(element):
                        continue
                        
                    if element not in prioritized_elements:
                        element_data = {
                            'element': element,
                            'tag': element.name,
                            'selectors': self.extract_smart_selectors(element),
                            'context': self.extract_element_context(element),
                            'html': str(element)[:300]  # Truncated HTML
                        }
                        # Only add if we got valid selectors
                        if element_data['selectors']:
                            prioritized_elements.append(element_data)
            except Exception as e:
                self.logger.debug(f"Error processing selector {selector}: {e}")
        
        return prioritized_elements[:20]  # Limit to top 20 elements
    
    def process_html_intelligently(self, html, last_action=None):
        """Main processing method that returns focused, actionable HTML summary"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove noise AND cookie banners
            for tag in soup(['script', 'style', 'noscript', 'meta', 'link']):
                tag.decompose()
                
            # Remove cookie consent elements specifically
            for element in soup.find_all(attrs={'id': re.compile(r'cookie|consent|privacy|gdpr|vendor-search', re.I)}):
                element.decompose()
            for element in soup.find_all(attrs={'class': re.compile(r'cookie|consent|privacy|gdpr|vendor-search', re.I)}):
                element.decompose()
            
            # Remove common overlay/modal structures that contain cookies
            for element in soup.find_all(['div', 'section', 'aside'], 
                                    attrs={'role': re.compile(r'dialog|alertdialog', re.I)}):
                if any(term in str(element).lower() for term in ['cookie', 'consent', 'privacy']):
                    element.decompose()
            
            # Analyze page intent
            page_intent = self.analyze_page_intent(soup)
            
            # Get prioritized interactive elements
            prioritized_elements = self.prioritize_content(soup, page_intent)
            
            # Build focused HTML summary
            summary_parts = []
            
            # Page context
            title = soup.find('title')
            if title:
                summary_parts.append(f"<title>{title.get_text(strip=True)}</title>")
            
            # Main content indicators
            if page_intent != "general":
                summary_parts.append(f"<!-- PAGE TYPE: {page_intent.upper()} -->")
            
            # Add prioritized elements with enhanced context
            summary_parts.append("<!-- INTERACTIVE ELEMENTS (PRIORITIZED, FILTERED) -->")
            
            for element_data in prioritized_elements:
                element = element_data['element']
                context = element_data['context']
                selectors = element_data['selectors']
                
                # Create enhanced element representation
                element_summary = f"<!-- ELEMENT: {element.name.upper()}"
                if context.get('purpose'):
                    element_summary += f" | PURPOSE: {context['purpose']}"
                if context.get('label'):
                    element_summary += f" | LABEL: {context['label']}"
                if context.get('current_value'):
                    element_summary += f" | VALUE: {context['current_value']}"
                element_summary += " -->\n"
                
                # Add best selector as comment
                if selectors:
                    best_selector = selectors[0]
                    element_summary += f"<!-- BEST_SELECTOR: {best_selector['selector']} (reliability: {best_selector['reliability']}%) -->\n"
                
                # Add cleaned element HTML
                element_summary += element_data['html'] + "\n\n"
                
                summary_parts.append(element_summary)
            
            # Combine and truncate if necessary
            final_html = '\n'.join(summary_parts)
            
            if len(final_html) > SYSTEM_CONFIG["html_truncate_length"]:
                # Intelligent truncation - keep most important elements
                truncated = final_html[:SYSTEM_CONFIG["html_truncate_length"]]
                last_comment = truncated.rfind('<!-- ELEMENT:')
                if last_comment > len(truncated) * 0.7:
                    final_html = truncated[:last_comment] + "\n<!-- [Content truncated - showing most relevant elements] -->"
                else:
                    final_html = truncated + "\n<!-- [Content truncated] -->"
            
            return {
                'html': final_html,
                'page_intent': page_intent,
                'element_count': len(prioritized_elements),
                'processing_stats': {
                    'original_length': len(html),
                    'processed_length': len(final_html),
                    'compression_ratio': len(final_html) / len(html) if len(html) > 0 else 0
                }
            }
            
        except Exception as e:
            self.logger.error(f"HTML processing failed: {e}")
            # Fallback to simple truncation
            return {
                'html': html[:SYSTEM_CONFIG["html_truncate_length"]],
                'page_intent': 'unknown',
                'element_count': 0,
                'processing_stats': {'error': str(e)}
            }

class EnhancedActionExecutor:
    """Enhanced action executor with improved button clicking"""
    
    def __init__(self, page):
        self.page = page
        self.timeout = BROWSER_CONFIG["timeout"]
        self.logger = EnhancedLogger()
    
    async def execute_action(self, action_data):
        """Execute action with enhanced reliability"""
        try:
            action_type = action_data.get("action")
            target = action_data.get("target")
            text = action_data.get("text", "")
            
            if action_type not in SUPPORTED_ACTIONS:
                raise ValueError(f"Unsupported action: {action_type}")
            
            self.logger.info(f"Executing: {action_type} on {target}")
            
            if action_type == "click":
                return await self._enhanced_click(target)
            elif action_type == "navigate":
                return await self._navigate(target)
            elif action_type == "type":
                return await self._type(target, text)
            elif action_type == "scroll":
                return await self._scroll(target)
            elif action_type == "wait":
                return await self._wait(target)
            elif action_type == "ask":
                return self._ask(text)
            elif action_type == "tell":
                return self._tell(text)
            elif action_type == "none":
                return {"success": True, "message": "Task completed"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _enhanced_click(self, selector):
        """Enhanced click with multiple strategies and fallbacks"""
        strategies = [
            self._click_by_selector,
            self._click_by_text_match,
            self._click_by_position,
            self._click_by_js_execution
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                self.logger.debug(f"Trying click strategy {i+1}: {strategy.__name__}")
                result = await strategy(selector)
                if result["success"]:
                    return result
            except Exception as e:
                self.logger.debug(f"Strategy {i+1} failed: {e}")
                continue
        
        return {"success": False, "error": f"All click strategies failed for selector: {selector}"}
    
    async def _click_by_selector(self, selector):
        """Standard selector-based clicking with better element detection"""
        try:
            # Check if page is still alive
            if self.page.is_closed():
                raise Exception("Page has been closed")
            
            # For search-related selectors, try OpenTable-specific elements first
            if "search" in selector.lower() or "input" in selector.lower():
                # Try OpenTable-specific search elements in order of preference
                ot_selectors = [
                    'input[data-testid="typeahead-input"]',
                    'input[placeholder*="restaurant" i]:visible:not([id*="cookie"])',
                    'input[placeholder*="location" i]:visible:not([id*="cookie"])',
                    'input[class*="search" i]:visible:not([id*="cookie"]):not([id*="vendor"])',
                    'input[type="search"]:visible:not([id*="cookie"]):not([id*="vendor"])',
                    'input[type="text"]:visible:not([id*="cookie"]):not([id*="vendor"])',
                    selector
                ]
                
                for ot_selector in ot_selectors:
                    try:
                        # Wait for element with shorter timeout for each attempt
                        await self.page.wait_for_selector(ot_selector, timeout=5000, state='visible')
                        element = await self.page.query_selector(ot_selector)
                        
                        if element:
                            # Double-check visibility and that it's not a cookie element
                            is_visible = await element.is_visible()
                            element_html = await element.inner_html()
                            
                            if is_visible and not any(term in element_html.lower() for term in ['cookie', 'vendor-search']):
                                await element.scroll_into_view_if_needed()
                                await asyncio.sleep(0.5)
                                await element.click(force=True)
                                await asyncio.sleep(1)
                                return {"success": True, "message": f"Successfully clicked: {ot_selector}"}
                    except Exception as e:
                        self.logger.debug(f"OpenTable selector {ot_selector} failed: {e}")
                        continue
            
            # Fallback to original selector logic
            await self.page.wait_for_selector(selector, timeout=self.timeout, state='visible')
            
            element = await self.page.query_selector(selector)
            if not element:
                raise Exception("Element not found after wait")
            
            # Check if element is enabled and visible
            is_visible = await element.is_visible()
            is_enabled = await element.is_enabled()
            
            if not is_visible:
                raise Exception("Element is not visible")
            if not is_enabled:
                raise Exception("Element is not enabled")
            
            # Final check that it's not a cookie element
            element_html = await element.inner_html()
            if any(term in element_html.lower() for term in ['cookie', 'vendor-search', 'privacy']):
                raise Exception("Element appears to be cookie/privacy related")
            
            # Scroll element into view if needed
            await element.scroll_into_view_if_needed()
            
            # Wait a moment for any animations
            await asyncio.sleep(0.5)
            
            # Click with force if needed
            await element.click(force=True)
            
            # Wait for action to complete
            await asyncio.sleep(1)
            
            return {"success": True, "message": f"Successfully clicked: {selector}"}
            
        except Exception as e:
            raise Exception(f"Click failed: {str(e)}")
    
    async def _click_by_text_match(self, selector):
        """Click by matching button/link text when selector fails"""
        # Extract text from selector if it contains text indicators
        text_patterns = [
            r'contains\(\s*[\'"]([^\'"]+)[\'"]\s*\)',  # xpath contains
            r'\[.*[\'"]([^\'"]*book[^\'"]*)[\'"].*\]',  # contains 'book'
            r'\[.*[\'"]([^\'"]*reserve[^\'"]*)[\'"].*\]',  # contains 'reserve'
            r'\[.*[\'"]([^\'"]*submit[^\'"]*)[\'"].*\]',  # contains 'submit'
        ]
        
        search_text = None
        for pattern in text_patterns:
            match = re.search(pattern, selector, re.I)
            if match:
                search_text = match.group(1)
                break
        
        if not search_text:
            # Try to find button-like elements with common action text
            action_texts = ['book', 'reserve', 'search', 'submit', 'find', 'go']
            for text in action_texts:
                elements = await self.page.query_selector_all(f"button:has-text('{text}'), input[value*='{text}'], a:has-text('{text}')")
                if elements:
                    await elements[0].click()
                    await asyncio.sleep(1)
                    return {"success": True, "message": f"Clicked element with text: {text}"}
        else:
            # Try to find element with matching text
            elements = await self.page.query_selector_all(f"button:has-text('{search_text}'), input[value*='{search_text}'], a:has-text('{search_text}')")
            if elements:
                await elements[0].click()
                await asyncio.sleep(1)
                return {"success": True, "message": f"Clicked element with text: {search_text}"}
        
        raise Exception("No matching text elements found")
    
    async def _click_by_position(self, selector):
        """Click by element position when other methods fail"""
        # This is a fallback method - try to find the element and click its center
        element = await self.page.query_selector(selector)
        if not element:
            raise Exception("Element not found for position click")
        
        # Get element bounding box
        box = await element.bounding_box()
        if not box:
            raise Exception("Could not get element position")
        
        # Click at center of element
        center_x = box['x'] + box['width'] / 2
        center_y = box['y'] + box['height'] / 2
        
        await self.page.mouse.click(center_x, center_y)
        await asyncio.sleep(1)
        
        return {"success": True, "message": f"Clicked at position: {center_x}, {center_y}"}
    
    async def _click_by_js_execution(self, selector):
        """Click using JavaScript execution as last resort"""
        script = f"""
        const element = document.querySelector('{selector}');
        if (element) {{
            element.scrollIntoView();
            element.focus();
            element.click();
            return true;
        }}
        return false;
        """
        
        result = await self.page.evaluate(script)
        if result:
            await asyncio.sleep(1)
            return {"success": True, "message": f"JS clicked: {selector}"}
        else:
            raise Exception("JavaScript click failed")
    
    async def _navigate(self, url):
        """Navigate to URL"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        await self.page.goto(url, timeout=self.timeout, wait_until='domcontentloaded')
        await asyncio.sleep(2)  # Wait for dynamic content
        
        return {"success": True, "message": f"Navigated to {url}"}
    
    async def _type(self, selector, text):
        """Type text with enhanced reliability"""
        await self.page.wait_for_selector(selector, timeout=self.timeout)
        
        # Clear field first
        await self.page.fill(selector, "")
        await asyncio.sleep(0.5)
        
        # Type with realistic delay
        await self.page.type(selector, text, delay=50)
        await asyncio.sleep(1)
        
        return {"success": True, "message": f"Typed '{text}' into {selector}"}
    
    async def _scroll(self, direction):
        """Scroll page"""
        if direction == "up":
            await self.page.keyboard.press("PageUp")
        elif direction == "down":
            await self.page.keyboard.press("PageDown")
        else:
            return {"success": False, "error": f"Invalid scroll direction: {direction}"}
        
        await asyncio.sleep(1)
        return {"success": True, "message": f"Scrolled {direction}"}
    
    async def _wait(self, seconds):
        """Wait for specified time"""
        wait_time = min(float(seconds), 10)  # Cap at 10 seconds
        await asyncio.sleep(wait_time)
        return {"success": True, "message": f"Waited {wait_time} seconds"}
    
    def _ask(self, text):
        """Ask user a question"""
        self.logger.info(f"AI asks: {text}")
        return {"success": True, "message": f"Asked: {text}"}
    
    def _tell(self, text):
        """Tell user something"""
        self.logger.info(f"AI says: {text}")
        return {"success": True, "message": f"Told: {text}"}

class EnhancedLLMClient:
    """Enhanced LLM client with better prompting"""
    
    def __init__(self):
        config = LLM_CONFIG["deepseek"]
        self.client = openai.OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"]
        )
        self.model = config["model"]
        self.max_tokens = config["max_tokens"]
        self.temperature = config["temperature"]
        self.logger = EnhancedLogger()
    
    def extract_json_from_response(self, content):
        """Enhanced JSON extraction"""
        if not content:
            raise ValueError("Empty response")
        
        # Try direct JSON parse first
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass
        
        # Look for JSON in markdown code blocks
        json_pattern = r'```json\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, content, re.DOTALL)
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass
        
        # Look for any JSON-like structure
        brace_count = 0
        start_idx = -1
        for i, char in enumerate(content):
            if char == '{':
                if start_idx == -1:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    try:
                        return json.loads(content[start_idx:i+1])
                    except json.JSONDecodeError:
                        start_idx = -1
        
        raise ValueError(f"No valid JSON found in response: {content[:200]}...")
    
    async def get_action(self, processed_html_data, task, history_context=""):
        """Get next action with enhanced context"""
        try:
            html = processed_html_data['html']
            page_intent = processed_html_data['page_intent']
            element_count = processed_html_data['element_count']
            
            # Build enhanced system prompt
            system_prompt = f"""You are an expert web automation AI. Your task is to complete: "{task}"

CURRENT PAGE ANALYSIS:
- Page Type: {page_intent}
- Interactive Elements Found: {element_count}
- Processing: {processed_html_data.get('processing_stats', {}).get('compression_ratio', 0):.1%} of original HTML retained

CRITICAL INSTRUCTIONS:
1. Use ONLY the selectors provided in "BEST_SELECTOR" comments - these are highly reliable
2. For reservations: look for party size, date, time, and booking buttons in that order
3. Always verify current form values before making changes
4. Use "none" action ONLY when the task is completely finished
5. Respond with ONLY valid JSON - no markdown, no explanations

Available actions: click, navigate, type, scroll, wait, ask, tell, none"""

            user_prompt = f"""HTML Content (processed for your task):
{html}

{history_context}

Analyze the page and decide your next action to progress toward: "{task}"

Respond with JSON only:
{{
  "action": "click|navigate|type|scroll|wait|ask|tell|none",
  "target": "selector or URL",
  "text": "text to type or message to user",
  "reasoning": "why this action progresses the task"
}}"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            content = response.choices[0].message.content.strip()
            self.logger.debug(f"LLM Response: {content[:200]}...")
            
            action_data = self.extract_json_from_response(content)
            return {"success": True, "action": action_data}
            
        except Exception as e:
            self.logger.error(f"LLM request failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def handle_error(self, html, error_message, task):
        """Handle errors with recovery suggestions"""
        try:
            prompt = f"""Error occurred while trying to complete: "{task}"

Current page HTML:
{html}

Error: {error_message}

Suggest a recovery action. Common solutions:
- Try alternative selectors (id, name, class, text-based)
- Wait for elements to load
- Scroll to make elements visible
- Navigate to correct page if wrong page

Respond with JSON only:
{{
  "action": "click|navigate|type|scroll|wait|ask|tell|none",
  "target": "alternative selector or URL",
  "text": "text if needed",
  "reasoning": "recovery strategy"
}}"""

            messages = [
                {"role": "system", "content": "You are a web automation error recovery expert. Provide practical solutions."},
                {"role": "user", "content": prompt}
            ]
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=1024,
                temperature=0.1
            )
            
            content = response.choices[0].message.content.strip()
            action_data = self.extract_json_from_response(content)
            return {"success": True, "action": action_data}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

class OptimizedComputerUseAI:
    """Main optimized AI system"""
    
    def __init__(self):
        self.logger = EnhancedLogger()
        self.html_processor = SmartHTMLProcessor()
        self.llm_client = EnhancedLLMClient()
        self.action_executor = None
        self.browser = None
        self.page = None
        self.history = []
    
    async def initialize_browser(self):
        """Initialize browser with anti-detection and error handling"""
        try:
            playwright = await async_playwright().start()
            
            self.browser = await playwright.chromium.launch(
                headless=False,  # Make browser visible
                args=[
                    '--no-blink-features=AutomationControlled',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--no-sandbox',
                    '--disable-http2',  # Disable HTTP2 to avoid protocol errors
                    '--disable-features=VizDisplayCompositor',
                    '--ignore-certificate-errors',
                    '--ignore-ssl-errors',
                    '--ignore-certificate-errors-spki-list'
                ]
            )
            
            context = await self.browser.new_context(
                viewport=BROWSER_CONFIG["viewport"],
                user_agent=BROWSER_CONFIG["user_agent"],
                ignore_https_errors=True,  # Ignore HTTPS errors
                java_script_enabled=True
            )
            
            self.page = await context.new_page()
            
            # Anti-detection scripts
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                // Override chrome detection
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                // Override languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
            """)
            
            self.action_executor = EnhancedActionExecutor(self.page)
            self.logger.info("Browser initialized successfully (visible mode)")
            return True
            
        except Exception as e:
            self.logger.error(f"Browser initialization failed: {e}")
            return False
    
    async def human_like_delay(self):
        """Add human-like delay"""
        if SYSTEM_CONFIG.get("human_like_delays", True):
            delay = random.uniform(SYSTEM_CONFIG["min_delay"], SYSTEM_CONFIG["max_delay"])
            await asyncio.sleep(delay)
    
    def build_history_context(self):
        """Build concise history context"""
        if not self.history:
            return "This is your first action. Focus on the task goal."
        
        recent_actions = self.history[-5:]  # Last 5 actions
        context_parts = [f"Recent actions taken ({len(recent_actions)} of {len(self.history)} total):"]
        
        for entry in recent_actions:
            action = entry['action']
            result = entry['result']
            status = "✓" if entry['success'] else "✗"
            context_parts.append(
                f"Step {entry['step']}: {status} {action.get('action')} "
                f"on '{action.get('target', 'N/A')}' - {result.get('message', result.get('error', 'No details'))}"
            )
        
        success_rate = sum(1 for entry in self.history if entry['success']) / len(self.history) * 100
        context_parts.append(f"Success rate: {success_rate:.0f}% ({len(self.history)} total actions)")
        
        return "\n".join(context_parts)
    
    async def run_task(self, task=None, start_url=None):
        """Run the complete task"""
        if not task:
            task = DEFAULT_TASK
        if not start_url:
            start_url = START_URL
        
        self.logger.info(f"Starting task: {task}")
        self.logger.info(f"Starting URL: {start_url}")
        
        if not await self.initialize_browser():
            return False
        
        try:
            # Navigate to starting page with retries and error handling
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.logger.info(f"Navigation attempt {attempt + 1} to: {start_url}")
                    await self.page.goto(
                        start_url, 
                        wait_until='domcontentloaded',
                        timeout=60000  # Increase timeout to 60 seconds
                    )
                    await asyncio.sleep(3)  # Wait for dynamic content
                    self.logger.info("Successfully navigated to starting page")
                    break
                except Exception as nav_error:
                    self.logger.warning(f"Navigation attempt {attempt + 1} failed: {nav_error}")
                    if attempt == max_retries - 1:
                        # Try alternative URL as fallback
                        fallback_url = "https://www.opentable.com/s?covers=4&dateTime=2025-08-26T19%3A00%3A00.000Z&latitude=35.2271&longitude=-80.8431&metroId=20&regionIds%5B%5D=363&term=italian"
                        self.logger.info(f"Trying fallback URL: {fallback_url}")
                        try:
                            await self.page.goto(fallback_url, wait_until='domcontentloaded', timeout=60000)
                            await asyncio.sleep(3)
                            break
                        except Exception as fallback_error:
                            self.logger.error(f"Fallback navigation also failed: {fallback_error}")
                            return False
                    else:
                        await asyncio.sleep(2)  # Wait before retry
            
            # Main execution loop
            for step in range(SYSTEM_CONFIG["max_steps"]):
                self.logger.info(f"\n=== STEP {step + 1} ===")
                
                try:
                    # Get and process HTML
                    raw_html = await self.page.content()
                    processed_data = self.html_processor.process_html_intelligently(raw_html)
                    
                    self.logger.info(f"Page type: {processed_data['page_intent']}, "
                                f"Elements: {processed_data['element_count']}, "
                                f"Compression: {processed_data['processing_stats'].get('compression_ratio', 0):.1%}")
                    
                    # Build history context
                    history_context = self.build_history_context()
                    
                    # Get action from LLM
                    llm_response = await self.llm_client.get_action(processed_data, task, history_context)
                    
                    if not llm_response["success"]:
                        self.logger.error(f"LLM failed: {llm_response['error']}")
                        continue
                    
                    action_data = llm_response["action"]
                    self.logger.info(f"Action: {action_data}")
                    
                    # Check for completion
                    if action_data.get("action") == "none":
                        self.logger.info("Task completed successfully!")
                        return True
                    
                    # Handle user interaction actions
                    if action_data.get("action") == "ask":
                        user_response = input(f"AI asks: {action_data.get('text')}\nYour response: ")
                        result = {"success": True, "message": f"User responded: {user_response}"}
                        self.add_to_history(step + 1, action_data, result)
                        continue
                    
                    if action_data.get("action") == "tell":
                        print(f"AI says: {action_data.get('text')}")
                        result = {"success": True, "message": f"Told user: {action_data.get('text')}"}
                        self.add_to_history(step + 1, action_data, result)
                        continue
                    
                    # Add human-like delay
                    await self.human_like_delay()
                    
                    # Execute action
                    result = await self.action_executor.execute_action(action_data)
                    self.logger.info(f"Result: {result}")
                    
                    # Wait for page to stabilize
                    if result.get("success"):
                        await asyncio.sleep(2)
                    
                    # Add to history
                    self.add_to_history(step + 1, action_data, result)
                    
                    # Handle errors
                    if not result["success"]:
                        self.logger.warning("Action failed, attempting recovery...")
                        recovery_response = await self.llm_client.handle_error(
                            processed_data['html'], result.get('error', ''), task
                        )
                        
                        if recovery_response["success"]:
                            recovery_action = recovery_response["action"]
                            self.logger.info(f"Recovery action: {recovery_action}")
                            
                            await self.human_like_delay()
                            recovery_result = await self.action_executor.execute_action(recovery_action)
                            self.add_to_history(step + 1.5, recovery_action, recovery_result)
                            
                            if recovery_result.get("success"):
                                await asyncio.sleep(2)
                    
                except KeyboardInterrupt:
                    self.logger.info("Task interrupted by user")
                    return False
                except Exception as e:
                    self.logger.error(f"Step {step + 1} failed: {e}")
                    
                    if SYSTEM_CONFIG["screenshot_on_error"]:
                        try:
                            await self.page.screenshot(path=f"error_step_{step + 1}.png")
                            self.logger.info(f"Error screenshot saved: error_step_{step + 1}.png")
                        except:
                            pass
                    continue
            
            self.logger.warning(f"Reached maximum steps ({SYSTEM_CONFIG['max_steps']}) without completion")
            return False

        finally:
            await self.cleanup()
    
    def add_to_history(self, step, action_data, result):
        """Add action to history"""
        self.history.append({
            'step': step,
            'timestamp': datetime.now().isoformat(),
            'action': action_data,
            'result': result,
            'success': result.get('success', False)
        })
    
    async def cleanup(self):
        """Clean up resources with proper error handling"""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
                # Give time for cleanup on Windows
                await asyncio.sleep(1)
            self.logger.info("Browser closed successfully")
        except Exception as e:
            self.logger.warning(f"Cleanup warning (non-fatal): {e}")
            # Don't raise the error, just log it

async def main():
    """Main entry point"""
    print("Enhanced Computer Use AI - Starting...")
    
    task = DEFAULT_TASK
    start_url = START_URL
    
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        print(f"Custom task: {task}")
    
    ai_system = OptimizedComputerUseAI()
    success = await ai_system.run_task(task, start_url)
    
    if success:
        print("\n✓ Task completed successfully!")
        return 0
    else:
        print("\n✗ Task failed or incomplete.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)