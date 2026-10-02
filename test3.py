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

# ================================
# CONFIGURATION CONSTANTS
# ================================

# DEBUG SETTINGS
DEBUG_HTML_PROCESSING = True  # Set to True to see HTML input/output during processing
SAVE_DEBUG_HTML_FILES = True  # Set to True to save HTML files to disk
DEBUG_OUTPUT_DIR = "debug_html"  # Directory for debug HTML files

# LLM CONFIGURATION
LLM_PROVIDER = "deepseek"
LLM_API_KEY = os.environ["DEEPSEEK_API_KEY"]
LLM_BASE_URL = "https://api.deepseek.com"
LLM_MODEL = "deepseek-chat"
LLM_MAX_TOKENS = 8192
LLM_TEMPERATURE = 0.1

# BROWSER CONFIGURATION
BROWSER_HEADLESS = False  # Set to True to hide browser window
BROWSER_WIDTH = 1280
BROWSER_HEIGHT = 720
BROWSER_TIMEOUT = 15000  # Reduce from 30000 to 15000ms
BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
BROWSER_IGNORE_HTTPS_ERRORS = True
BROWSER_IGNORE_AUTOMATION = True

# SYSTEM BEHAVIOR
MAX_EXECUTION_STEPS = 50
HTML_TRUNCATE_LENGTH = 20000
SCREENSHOT_ON_ERROR = True
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
HUMAN_LIKE_DELAYS = True
MIN_DELAY_SECONDS = 2
MAX_DELAY_SECONDS = 4

# TASK DEFAULTS
DEFAULT_TASK = "book a reservation for 4 at pf changs"
START_URL = "https://www.google.com"
FALLBACK_URL = "https://www.google.com"

# NAVIGATION SETTINGS
MAX_NAVIGATION_RETRIES = 3
NAVIGATION_TIMEOUT = 60000  # milliseconds
PAGE_LOAD_WAIT_TIME = 3  # seconds to wait after page loads

# HTML PROCESSING SETTINGS
MAX_PRIORITIZED_ELEMENTS = 100  # Increase from 20 to capture more elements
MAX_ELEMENT_HTML_LENGTH = 400  # Increase from 300 to see more HTML
MAX_NEARBY_TEXT_LENGTH = 100  # Increase from 100
MAX_LABEL_TEXT_LENGTH = 150  # Add this missing constant
WAIT_FOR_DYNAMIC_CONTENT = True  # New constant to wait for dynamic content
DYNAMIC_CONTENT_WAIT_TIME = 3  # Seconds to wait for dynamic content after actions

# ERROR HANDLING
MAX_CLICK_STRATEGIES = 4
ELEMENT_WAIT_TIMEOUT = 3000  # Reduce from 5000 to 3000ms for faster failures
POST_ACTION_WAIT_TIME = 0.5  # Reduce from 1 to 0.5 seconds
PAGE_STABILIZE_WAIT_TIME = 1  # Reduce from 2 to 1 second
FAST_ELEMENT_TIMEOUT = 1000  # New: Quick timeout for element checks
SLOW_ELEMENT_TIMEOUT = 8000  # New: Slower timeout for important elements

# SUPPORTED ACTIONS
SUPPORTED_ACTIONS = ["click", "navigate", "type", "scroll", "wait", "none", "ask", "tell"]

# ================================
# DERIVED CONFIGURATIONS
# ================================

LLM_CONFIG = {
    "deepseek": {
        "api_key": LLM_API_KEY,
        "base_url": LLM_BASE_URL,
        "model": LLM_MODEL,
        "max_tokens": LLM_MAX_TOKENS,
        "temperature": LLM_TEMPERATURE
    }
}

BROWSER_CONFIG = {
    "headless": BROWSER_HEADLESS,
    "viewport": {"width": BROWSER_WIDTH, "height": BROWSER_HEIGHT},
    "timeout": BROWSER_TIMEOUT,
    "user_agent": BROWSER_USER_AGENT,
    "ignore_https_errors": BROWSER_IGNORE_HTTPS_ERRORS,
    "ignore_default_args": ["--enable-automation"] if BROWSER_IGNORE_AUTOMATION else []
}

SYSTEM_CONFIG = {
    "llm_provider": LLM_PROVIDER,
    "max_steps": MAX_EXECUTION_STEPS,
    "html_truncate_length": HTML_TRUNCATE_LENGTH,
    "screenshot_on_error": SCREENSHOT_ON_ERROR,
    "log_level": LOG_LEVEL,
    "human_like_delays": HUMAN_LIKE_DELAYS,
    "min_delay": MIN_DELAY_SECONDS,
    "max_delay": MAX_DELAY_SECONDS
}

# ================================
# CLASSES
# ================================

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
        
        # Setup debug directory if needed
        if SAVE_DEBUG_HTML_FILES and not os.path.exists(DEBUG_OUTPUT_DIR):
            os.makedirs(DEBUG_OUTPUT_DIR)
        
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
        
    def debug_print_html(self, title, html_content, step=None):
        """Print HTML content for debugging"""
        if not DEBUG_HTML_PROCESSING:
            return
            
        separator = "=" * 80
        print(f"\n{separator}")
        print(f"DEBUG HTML - {title}")
        if step:
            print(f"Step: {step}")
        print(f"Length: {len(html_content)} characters")
        print(separator)
        print(html_content[:2000] + ("..." if len(html_content) > 2000 else ""))
        print(separator)
        
        # Save to file if enabled
        if SAVE_DEBUG_HTML_FILES:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{DEBUG_OUTPUT_DIR}/{timestamp}_{title.replace(' ', '_')}.html"
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"DEBUG: HTML saved to {filename}")
            except Exception as e:
                print(f"DEBUG: Failed to save HTML to file: {e}")
                
    def format_prioritized_elements(self, prioritized_elements):
        """Format prioritized elements for LLM consumption with better search result info"""
        formatted_elements = []
        
        for i, element_data in enumerate(prioritized_elements):
            element = element_data['element']
            tag = element_data['tag']
            selectors = element_data['selectors']
            context = element_data['context']
            
            # Create element description
            element_info = []
            
            # Add element type and key attributes
            element_info.append(f"ELEMENT: {tag.upper()}")
            
            # Add special info for links
            if tag == 'a' and 'href' in element_data:
                href = element_data['href']
                text = element_data.get('text', '')
                element_info.append(f"LINK_TEXT: {text[:100]}")
                element_info.append(f"URL: {href[:150]}")
                
                # Highlight relevant links
                if any(term in href.lower() for term in ['opentable', 'reservation']):
                    element_info.append("*** RELEVANT FOR BOOKING ***")
            
            # Add other element attributes
            for attr in ['aria-label', 'placeholder', 'value', 'title', 'data-test']:
                if element.get(attr):
                    element_info.append(f"{attr.upper()}: {element.get(attr)}")
            
            # Add purpose if identified
            purpose = self.identify_element_purpose(element)
            if purpose:
                element_info.append(f"PURPOSE: {purpose}")
            
            # Add context
            if context and context != "No nearby text found":
                element_info.append(f"CONTEXT: {context}")
            
            # Add best selector
            if selectors:
                best_selector = selectors[0]
                reliability = self.calculate_selector_reliability(best_selector, element)
                element_info.append(f"BEST_SELECTOR: {best_selector} (reliability: {reliability}%)")
            
            # Format the complete element
            element_header = " | ".join(element_info)
            element_html = element_data['html']
            
            formatted_elements.append(f"<!-- {element_header} -->")
            formatted_elements.append(element_html)
            formatted_elements.append("")  # Empty line for readability
        
        return "\n".join(formatted_elements)
                
    def process_google_search_results(self, soup):
        """Special processing for Google search results pages"""
        prioritized_elements = []
        
        # Google search result patterns
        search_result_selectors = [
            # Main search result links
            'h3 a[href*="opentable"]',
            'a[href*="opentable.com"]',
            'a[data-ved]',  # Google result links
            'div[data-hveid] a',  # Links within result containers
            'cite[role="text"]',  # URL display elements (can help identify results)
            
            # Search result containers
            'div[data-hveid]',  # Individual search results
            'div[jsname]',  # Google dynamic elements
            
            # Navigation and search
            'input[type="text"]:not([type="hidden"])',
            'textarea[aria-label*="Search" i]',
            'button[aria-label*="Search" i]',
            'input[type="submit"]',
            
            # All visible links (fallback)
            'a[href]:not([href*="google.com/search"]):not([href*="accounts.google"]):not([href*="policies.google"])',
        ]
        
        # Extract search results with better context
        for selector in search_result_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    # Skip if already processed
                    if any(elem['element'] == element for elem in prioritized_elements):
                        continue
                    
                    # Get link URL and text for context
                    href = element.get('href', '')
                    text_content = element.get_text(strip=True)[:200]
                    
                    # Filter out irrelevant links
                    if any(skip_term in href.lower() for skip_term in [
                        'google.com/search', 'accounts.google', 'policies.google', 
                        'support.google', 'maps.google', 'translate.google'
                    ]):
                        continue
                    
                    # Prioritize OpenTable links
                    priority_score = 0
                    if 'opentable' in href.lower() or 'opentable' in text_content.lower():
                        priority_score += 100
                    if any(term in text_content.lower() for term in ['reservation', 'book', 'table', 'restaurant']):
                        priority_score += 50
                    if any(term in text_content.lower() for term in ['pf chang', "chang's", 'pf chang']):
                        priority_score += 75
                    
                    element_data = {
                        'element': element,
                        'tag': element.name,
                        'selectors': self.extract_smart_selectors(element),
                        'context': f"LINK: {text_content} | URL: {href[:100]}",
                        'html': str(element)[:MAX_ELEMENT_HTML_LENGTH],
                        'priority': priority_score,
                        'href': href,
                        'text': text_content
                    }
                    
                    prioritized_elements.append(element_data)
            except Exception as e:
                self.logger.debug(f"Error processing search selector {selector}: {e}")
        
        # Sort by priority score
        prioritized_elements.sort(key=lambda x: x.get('priority', 0), reverse=True)
        
        return prioritized_elements[:MAX_PRIORITIZED_ELEMENTS]
                
    async def _find_relevant_alternatives(self, original_selector, action_context=""):
        """Find relevant alternative selectors based on context"""
        alternatives = []
        
        # If this looks like a Google search result selector
        if 'data-hveid' in original_selector or 'data-ved' in original_selector:
            alternatives = [
                'a[href*="opentable"]:visible',  # Direct OpenTable links
                'a[href*="reservation"]:visible',  # Reservation links
                'h3 a[href]:visible',  # Main result title links
                'a[data-ved]:visible',  # Any Google result link
                'div[data-hveid] a:visible',  # Links in result containers
                'a[href]:not([href*="google.com"]):visible',  # External links
                original_selector.replace('[data-hveid=', '[data-ved='),  # Try data-ved instead
                original_selector.replace(':visible', ''),  # Remove visibility requirement
            ]
        
        # If looking for links/navigation
        elif any(term in original_selector.lower() for term in ['href', 'link', 'data-hveid']):
            alternatives = [
                'a[href*="opentable"]:visible',  # OpenTable links
                'a[href*="restaurant"]:visible',  # Restaurant links
                'a[href*="reservation"]:visible',  # Reservation links
                'a[href*="book"]:visible',  # Booking links
                'h3 a[href]:visible',  # Search result title links
                'a[href]:visible',  # Any visible link
                'button[data-test*="book"]:visible',  # Booking buttons
                'button[data-test*="reserve"]:visible',  # Reserve buttons
                original_selector.replace(':visible', ''),  # Remove visibility requirement
                original_selector.replace(':not([id*="cookie"])', ''),  # Remove cookie filter
            ]
        
        # If looking for input fields
        elif any(term in original_selector.lower() for term in ['input', 'search', 'text']):
            alternatives = [
                'input[type="text"]:visible',
                'input[type="search"]:visible', 
                'input[placeholder*="restaurant" i]:visible',
                'input[placeholder*="search" i]:visible',
                'input[placeholder*="location" i]:visible',
                'input[data-testid*="search"]:visible',
                'input[data-test*="search"]:visible',
                'textarea:visible',
                'input[name="q"]:visible',  # Google search box
                original_selector.replace(':visible', ''),
                original_selector.replace(':not([id*="cookie"])', ''),
            ]
        
        # If looking for buttons
        elif 'button' in original_selector.lower():
            alternatives = [
                'button[type="submit"]:visible',
                'button[data-test*="search"]:visible',
                'button[data-test*="book"]:visible',
                'button[data-test*="reserve"]:visible',
                'button[aria-label*="search" i]:visible',
                'button[aria-label*="book" i]:visible',
                'input[type="submit"]:visible',
                'button:visible',  # Any visible button as last resort
                original_selector.replace(':visible', ''),
            ]
        
        # If looking for form elements
        elif any(term in original_selector.lower() for term in ['select', 'option']):
            alternatives = [
                'select:visible',
                'select[name*="party"]:visible',
                'select[name*="date"]:visible', 
                'select[name*="time"]:visible',
                'select[aria-label*="party" i]:visible',
                'select[aria-label*="date" i]:visible',
                'select[aria-label*="time" i]:visible',
                original_selector.replace(':visible', ''),
            ]
        
        # If looking for date/time elements
        elif any(term in original_selector.lower() for term in ['date', 'time', 'calendar']):
            alternatives = [
                'input[type="date"]:visible',
                'input[type="time"]:visible',
                'select[name*="date"]:visible',
                'select[name*="time"]:visible',
                'button[aria-label*="date" i]:visible',
                'button[aria-label*="time" i]:visible',
                'div[data-test*="date"]:visible',
                'div[data-test*="time"]:visible',
                original_selector.replace(':visible', ''),
            ]
        
        else:
            # Generic fallbacks for unknown selectors
            alternatives = [
                original_selector.replace(':visible', ''),  # Remove visibility requirement
                original_selector.replace(':not([id*="cookie"])', ''),  # Remove cookie filter
                original_selector.split(':')[0],  # Remove all pseudo-selectors
                original_selector.split('[')[0],  # Get just the tag name
            ]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_alternatives = []
        for alt in alternatives:
            if alt not in seen and alt != original_selector:
                seen.add(alt)
                unique_alternatives.append(alt)
        
        return unique_alternatives
    
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
            context['nearby_text'] = nearby_text[:MAX_NEARBY_TEXT_LENGTH]
        
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
                if text and len(text) < MAX_LABEL_TEXT_LENGTH:
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
                if parent_text and len(parent_text) < MAX_NEARBY_TEXT_LENGTH:
                    nearby_texts.append(parent_text)
                    break
            parent = parent.parent
            depth += 1
        
        return ' '.join(nearby_texts)
    
    def prioritize_content(self, soup, page_intent):
        """Prioritize content based on page intent and task relevance"""
        
        # Special handling for Google search results
        if 'search' in page_intent.lower() and ('google' in str(soup).lower() or 'data-hveid' in str(soup)):
            self.logger.info("Detected Google search results page - using specialized processing")
            return self.process_google_search_results(soup)
        
        # Regular processing for other pages
        prioritized_elements = []
        
        # Remove cookie banners and hidden elements first
        for element in soup.find_all(['div', 'section', 'aside'], attrs={'class': re.compile(r'cookie|consent|privacy|gdpr', re.I)}):
            element.decompose()
        for element in soup.find_all(attrs={'id': re.compile(r'cookie|consent|privacy|gdpr|vendor-search', re.I)}):
            element.decompose()
        
        # Enhanced priority selectors that are more inclusive
        priority_selectors = [
            # ALL input elements (most important for forms)
            'input:not([id*="cookie"]):not([class*="cookie"]):not([style*="display: none"])',
            'input[type="text"]:visible', 
            'input[type="search"]:visible',
            'input[placeholder*="search" i]:visible',
            'input[placeholder*="restaurant" i]:visible',
            'input[placeholder*="location" i]:visible',
            
            # Dynamic search elements (common patterns)
            '[data-testid*="search"]:not([id*="cookie"])',
            '[data-testid*="typeahead"]:not([id*="cookie"])',
            '[data-test*="search"]:not([id*="cookie"])',
            '[aria-label*="search" i]:not([id*="cookie"])',
            
            # All buttons (for navigation and actions)
            'button:not([id*="cookie"]):not([class*="cookie"])',
            'button[type="submit"]:not([id*="cookie"])',
            
            # Form elements
            'select:not([id*="cookie"])',
            'textarea:not([id*="cookie"])',
            
            # Links (for navigation)
            'a[href]:not([href*="cookie"]):not([href*="privacy"])',
            
            # Common OpenTable specific elements
            'button[data-test*="book"]',
            'button[data-test*="reserve"]',
            'select[name*="party"], select[name*="size"], select[name*="guest"]',
            'input[name*="date"], input[type="date"]',
            'select[name*="time"], input[type="time"]',
            
            # Form containers (to catch dynamically loaded forms)
            'form:not([id*="cookie"]):not([class*="cookie"])',
            'div[role="search"]:not([id*="cookie"])',
            'div[class*="search"]:not([class*="cookie"])'
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
                            'html': str(element)[:MAX_ELEMENT_HTML_LENGTH]
                        }
                        # Add element even if no smart selectors (for debugging)
                        prioritized_elements.append(element_data)
            except Exception as e:
                self.logger.debug(f"Error processing selector {selector}: {e}")
        
        return prioritized_elements[:MAX_PRIORITIZED_ELEMENTS]
    
    def process_html_intelligently(self, html, last_action=None, step=None):
        """Main processing method that returns focused, actionable HTML summary"""
        try:
            # Debug: Show input HTML
            self.debug_print_html("INPUT HTML", html, step)
            
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
            
            # Debug: Show output HTML
            self.debug_print_html("PROCESSED HTML (OUTPUT)", final_html, step)
            
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
        
    async def _quick_element_check(self, selector):
        """Quick check if element exists without long waits"""
        try:
            await self.page.wait_for_selector(selector, timeout=FAST_ELEMENT_TIMEOUT, state='visible')
            return True
        except:
            return False
    
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
        """Enhanced click with smart alternatives and fallbacks"""
        
        # Quick check first
        if not await self._quick_element_check(selector):
            self.logger.debug(f"Quick check failed for {selector}, trying relevant alternatives")
            
            # Try contextually relevant alternatives
            alternatives = await self._find_relevant_alternatives(selector)
            
            for alt_selector in alternatives:
                if await self._quick_element_check(alt_selector):
                    self.logger.info(f"Found relevant alternative: {alt_selector}")
                    selector = alt_selector
                    break
            else:
                self.logger.warning(f"No relevant alternatives found for {selector}")
        
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
            
            # Use faster timeout for initial check
            timeout_to_use = SLOW_ELEMENT_TIMEOUT if any(word in selector.lower() for word in ['input', 'search', 'text']) else FAST_ELEMENT_TIMEOUT
            
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
                    'input[type="text"]',  # Fallback without restrictions
                    'input[type="search"]',  # Fallback without restrictions
                    selector
                ]
                
                for ot_selector in ot_selectors:
                    try:
                        # Wait for element with shorter timeout for each attempt
                        await self.page.wait_for_selector(ot_selector, timeout=FAST_ELEMENT_TIMEOUT, state='visible')
                        element = await self.page.query_selector(ot_selector)
                        
                        if element:
                            # Double-check visibility and that it's not a cookie element
                            is_visible = await element.is_visible()
                            element_html = await element.inner_html()
                            
                            if is_visible and not any(term in element_html.lower() for term in ['cookie', 'vendor-search']):
                                await element.scroll_into_view_if_needed()
                                await asyncio.sleep(0.2)  # Reduced wait
                                await element.click(force=True)
                                await asyncio.sleep(POST_ACTION_WAIT_TIME)
                                return {"success": True, "message": f"Successfully clicked: {ot_selector}"}
                    except Exception as e:
                        self.logger.debug(f"OpenTable selector {ot_selector} failed: {e}")
                        continue
            
            # Fallback to original selector logic with faster timeout
            await self.page.wait_for_selector(selector, timeout=timeout_to_use, state='visible')
            
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
            
            # Reduced wait time
            await asyncio.sleep(0.2)
            
            # Click with force if needed
            await element.click(force=True)
            
            # Wait for action to complete
            await asyncio.sleep(POST_ACTION_WAIT_TIME)
            
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
                    await asyncio.sleep(POST_ACTION_WAIT_TIME)
                    return {"success": True, "message": f"Clicked element with text: {text}"}
        else:
            # Try to find element with matching text
            elements = await self.page.query_selector_all(f"button:has-text('{search_text}'), input[value*='{search_text}'], a:has-text('{search_text}')")
            if elements:
                await elements[0].click()
                await asyncio.sleep(POST_ACTION_WAIT_TIME)
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
        await asyncio.sleep(POST_ACTION_WAIT_TIME)
        
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
            await asyncio.sleep(POST_ACTION_WAIT_TIME)
            return {"success": True, "message": f"JS clicked: {selector}"}
        else:
            raise Exception("JavaScript click failed")
    
    async def _navigate(self, url):
        """Navigate to URL"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        await self.page.goto(url, timeout=self.timeout, wait_until='domcontentloaded')
        await asyncio.sleep(PAGE_STABILIZE_WAIT_TIME)
        
        return {"success": True, "message": f"Navigated to {url}"}
    
    async def _type(self, selector, text):
        """Type text with enhanced reliability"""
        await self.page.wait_for_selector(selector, timeout=self.timeout)
        
        # Clear field first
        await self.page.fill(selector, "")
        await asyncio.sleep(0.5)
        
        # Type with realistic delay
        await self.page.type(selector, text, delay=50)
        await asyncio.sleep(POST_ACTION_WAIT_TIME)
        
        return {"success": True, "message": f"Typed '{text}' into {selector}"}
    
    async def _scroll(self, direction):
        """Scroll page"""
        if direction == "up":
            await self.page.keyboard.press("PageUp")
        elif direction == "down":
            await self.page.keyboard.press("PageDown")
        else:
            return {"success": False, "error": f"Invalid scroll direction: {direction}"}
        
        await asyncio.sleep(POST_ACTION_WAIT_TIME)
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
        config = LLM_CONFIG[LLM_PROVIDER]
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
            
            # Build enhanced system prompt with better task understanding
            system_prompt = f"""You are an expert web automation AI specializing in restaurant reservations on OpenTable.

    YOUR MAIN TASK: {task}

    CURRENT SITUATION:
    - Page Type: {page_intent}
    - Available Interactive Elements: {element_count}
    - HTML Processing: {processed_html_data.get('processing_stats', {}).get('compression_ratio', 0):.1%} of original content shown

    RESERVATION BOOKING STRATEGY:
    1. FIRST: Find and search for the specific restaurant name
    2. SECOND: Select the correct restaurant from search results  
    3. THIRD: Choose party size (4 people)
    4. FOURTH: Select date (8/26/2025)
    5. FIFTH: Choose time (evening preferred)
    6. SIXTH: Complete the booking

    ELEMENT SELECTION RULES:
    - ALWAYS use the EXACT selector from "BEST_SELECTOR" comments
    - Look for restaurant names in links/buttons for navigation
    - Search inputs usually have placeholder text about restaurants/locations
    - Booking buttons often contain words like "Reserve", "Book", "Available"
    - Date/time selectors are usually dropdown menus or inputs

    CRITICAL: Only use "none" when you have successfully completed a reservation booking."""

            user_prompt = f"""CURRENT PAGE CONTENT:
    {html}

    RECENT HISTORY:
    {history_context}

    ANALYZE the page and determine your next action to progress toward: "{task}"

    Focus on:
    - Restaurant search functionality if not yet searched
    - Restaurant selection from results if on search results page  
    - Reservation form fields if on booking page
    - Navigation links to get to booking pages

    Respond ONLY with valid JSON:
    {{
    "action": "click|navigate|type|scroll|wait|ask|tell|none",
    "target": "EXACT selector from BEST_SELECTOR comments",
    "text": "text to type (only for type action)",
    "reasoning": "specific reason this action progresses the reservation booking"
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
            prompt = f"""ERROR RECOVERY for task: "{task}"

    Current page HTML:
    {html}

    Error that occurred: {error_message}

    RECOVERY STRATEGY NEEDED:
    Analyze what went wrong and suggest a better approach.

    Common solutions:
    1. If selector not found: Look for similar elements in the HTML above
    2. If wrong element clicked: Find the correct restaurant/booking link  
    3. If page didn't load: Try scrolling or waiting
    4. If navigation failed: Look for alternative navigation paths

    Focus on elements that will actually progress the restaurant reservation task.

    Respond with JSON only:
    {{
    "action": "click|navigate|type|scroll|wait|ask|tell|none",
    "target": "selector that actually exists in the HTML above",
    "text": "text if needed",
    "reasoning": "how this fixes the error and progresses the booking"
    }}"""

            messages = [
                {"role": "system", "content": "You are a web automation error recovery expert. Focus on finding working solutions that progress the actual task."},
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
                headless=BROWSER_HEADLESS,
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
                ignore_https_errors=BROWSER_CONFIG["ignore_https_errors"],
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
            headless_status = "headless" if BROWSER_HEADLESS else "visible"
            self.logger.info(f"Browser initialized successfully ({headless_status} mode)")
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
            for attempt in range(MAX_NAVIGATION_RETRIES):
                try:
                    self.logger.info(f"Navigation attempt {attempt + 1} to: {start_url}")
                    await self.page.goto(
                        start_url, 
                        wait_until='domcontentloaded',
                        timeout=NAVIGATION_TIMEOUT
                    )
                    await asyncio.sleep(PAGE_LOAD_WAIT_TIME)
                    self.logger.info("Successfully navigated to starting page")
                    break
                except Exception as nav_error:
                    self.logger.warning(f"Navigation attempt {attempt + 1} failed: {nav_error}")
                    if attempt == MAX_NAVIGATION_RETRIES - 1:
                        # Try alternative URL as fallback
                        self.logger.info(f"Trying fallback URL: {FALLBACK_URL}")
                        try:
                            await self.page.goto(FALLBACK_URL, wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT)
                            await asyncio.sleep(PAGE_LOAD_WAIT_TIME)
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
                    processed_data = self.html_processor.process_html_intelligently(raw_html, step=step+1)
                    
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
                    # Wait for page to stabilize and dynamic content to load
                    if result.get("success"):
                        await asyncio.sleep(PAGE_STABILIZE_WAIT_TIME)
                        # Extra wait for dynamic content after clicks
                        if action_data.get("action") == "click" and WAIT_FOR_DYNAMIC_CONTENT:
                            await asyncio.sleep(DYNAMIC_CONTENT_WAIT_TIME)
                    
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
                                await asyncio.sleep(PAGE_STABILIZE_WAIT_TIME)
                    
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