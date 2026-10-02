import re
from bs4 import BeautifulSoup
from config import SYSTEM_CONFIG
from logger import Logger

class HTMLProcessor:
    """Processes HTML for LLM consumption, focusing on text and interactive elements"""
    
    def __init__(self):
        self.truncate_length = SYSTEM_CONFIG["html_truncate_length"]
        self.print_to_console = SYSTEM_CONFIG.get("print_html_to_console", False)
        self.logger = Logger()
    
    def clean_html(self, html):
        """Clean HTML to retain only text and interactive elements"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove non-essential elements
            for tag in soup(["script", "style", "noscript", "svg", "img", "meta", "link", "head"]):
                tag.decompose()
            
            # Keep only text-heavy and interactive tags
            essential_tags = ['button', 'input', 'textarea', 'form', 'a', 
                              'h1', 'h2', 'h3', 'p', 'span', 'div', 'li', 'ul',
                              'strong', 'b', 'i', 'em', 'select', 'option', 'label']
            
            # Keep essential attributes
            essential_attrs = ['id', 'class', 'href', 'type', 'name', 'value', 'placeholder', 'aria-label', 'role', 'title', 'onclick']
            
            for tag in soup.find_all(True):  # find_all(True) gets all tags
                # Unwrap non-essential tags to keep their text content
                if tag.name not in essential_tags:
                    tag.unwrap()
                else:
                    attrs_to_keep = {attr: value for attr, value in tag.attrs.items() 
                                     if attr in essential_attrs}
                    tag.attrs = attrs_to_keep
            
            # Clean whitespace
            cleaned_html = str(soup)
            cleaned_html = re.sub(r'\s+', ' ', cleaned_html).strip()
            
            return cleaned_html
            
        except Exception as e:
            print(f"Error cleaning HTML: {e}")
            return html
    
    def truncate_html(self, html):
        """Truncate HTML to fit within token limits"""
        if len(html) <= self.truncate_length:
            return html
        truncated = html[:self.truncate_length]
        last_tag_end = truncated.rfind('>')
        if last_tag_end > self.truncate_length * 0.8:
            truncated = html[:last_tag_end + 1]
        return truncated + "\n... [HTML truncated]"
    
    def extract_interactive_elements(self, html):
        """Extract buttons, links, and input fields with more context"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            interactive_elements = []
            
            # Find a wider range of potentially clickable elements
            interactive_tags = soup.find_all(['a', 'button', 'input', 'textarea', 'select', 'div', 'span'])
            
            processed_selectors = set()
            
            for element in interactive_tags:
                selector = self._generate_selector(element)
                if selector in processed_selectors:
                    continue
                
                element_type = element.name
                
                if element_type == 'a' and element.get('href'):
                    text = element.get_text(strip=True) or element.get('aria-label', '') or element.get('title', '')
                    if text:
                        interactive_elements.append({
                            'type': 'link',
                            'text': text,
                            'href': element['href'],
                            'selector': selector
                        })
                elif element_type in ['button', 'input']:
                    if element.get('type') in ['button', 'submit']:
                        text = element.get_text(strip=True) or element.get('value', '') or element.get('aria-label', '') or element.get('title', '')
                        if text:
                            interactive_elements.append({
                                'type': 'button',
                                'text': text,
                                'selector': selector
                            })
                    elif element.get('type') in ['text', 'email', 'password', 'search', 'tel']:
                        label = self._get_label_for_input(element)
                        interactive_elements.append({
                            'type': 'input',
                            'placeholder': element.get('placeholder', ''),
                            'name': element.get('name', ''),
                            'label': label,
                            'selector': selector
                        })
                    elif element_type == 'select':
                        label = self._get_label_for_input(element)
                        interactive_elements.append({
                            'type': 'dropdown',
                            'name': element.get('name', ''),
                            'label': label,
                            'selector': selector
                        })
                elif element_type == 'textarea':
                    label = self._get_label_for_input(element)
                    interactive_elements.append({
                        'type': 'textarea',
                        'placeholder': element.get('placeholder', ''),
                        'name': element.get('name', ''),
                        'label': label,
                        'selector': selector
                    })
                # Catch-all for elements with click handlers or specific roles
                elif element.get('onclick') or element.get('role') in ['link', 'button']:
                    text = element.get_text(strip=True) or element.get('aria-label', '') or element.get('title', '')
                    if text:
                        interactive_elements.append({
                            'type': 'clickable',
                            'text': text,
                            'selector': selector
                        })
                        
                processed_selectors.add(selector)

            # Deduplicate by selector to avoid duplicates
            final_elements = {el['selector']: el for el in interactive_elements}.values()

            return list(final_elements)
            
        except Exception as e:
            print(f"Error extracting interactive elements: {e}")
            return []
    
    def _generate_selector(self, element):
        """Generate a more robust CSS selector favoring stable attributes"""
        # Special handling for Google search elements
        if element.get('name') == 'btnK' and element.get('type') == 'submit':
            return "input[name='btnK'][type='submit']"
        
        if element.get('name') == 'q':
            return f"{element.name}[name='q']"
        
        # Check for ID first (most reliable)
        if element.get('id'):
            return f"#{element['id']}"
        
        # Build selector based on stable attributes
        parts = [element.name]
        
        # Add stable attributes in order of preference
        stable_attributes = ['name', 'type', 'role', 'aria-label']
        for attr in stable_attributes:
            value = element.get(attr)
            if value:
                if attr == 'aria-label':
                    # Use contains for aria-label to handle variations
                    parts.append(f"[{attr}*='{value[:20]}']")  # Truncate long labels
                else:
                    parts.append(f"[{attr}='{value}']")
        
        # Only add href for links
        if element.name == 'a' and element.get('href'):
            href = element['href']
            if len(href) < 100:  # Only for reasonable length hrefs
                parts.append(f"[href='{href}']")
        
        # Only add classes as a last resort and prefer simple ones
        if not any('[' in part for part in parts[1:]):  # If no attributes were added
            classes = element.get('class', [])
            if classes:
                # Filter out likely dynamic classes (random characters, very long, etc.)
                stable_classes = []
                for cls in classes:
                    if (len(cls) <= 20 and  # Not too long
                        not re.match(r'^[a-zA-Z]{1,3}[0-9]+[a-zA-Z]*$', cls) and  # Not like "gNO89b"
                        not cls.isdigit()):  # Not just numbers
                        stable_classes.append(cls)
                
                if stable_classes:
                    class_str = '.'.join(stable_classes[:2])  # Max 2 classes
                    parts[0] = f"{element.name}.{class_str}"
        
        return "".join(parts)
    
    def extract_google_search_elements(self, soup):
        """
        Specifically extract Google search-related elements with better selectors
        """
        elements = []
        
        # Look for search input
        search_inputs = soup.find_all(['input', 'textarea'], attrs={'name': 'q'})
        for inp in search_inputs:
            elements.append({
                'type': 'search_input',
                'selector': f"input[name='q']" if inp.name == 'input' else f"textarea[name='q']",
                'placeholder': inp.get('placeholder', ''),
                'title': inp.get('title', 'Search input')
            })
        
        # Look for search buttons with multiple approaches
        search_buttons = soup.find_all('input', attrs={'type': 'submit'})
        for btn in search_buttons:
            if btn.get('name') == 'btnK' or 'Search' in str(btn.get('value', '')):
                elements.append({
                    'type': 'search_button',
                    'selector': f"input[name='btnK'][type='submit']",
                    'value': btn.get('value', ''),
                    'text': 'Google Search Button'
                })
        
        return elements

    def _get_label_for_input(self, input_element):
        """Find the associated label for an input element."""
        if input_element.get('id'):
            label = input_element.find_previous_sibling('label', attrs={'for': input_element['id']})
            if label:
                return label.get_text(strip=True)
        # Check for a parent label
        parent_label = input_element.find_parent('label')
        if parent_label:
            return parent_label.get_text(strip=True)
        return input_element.get('aria-label', '')
        
    def process(self, html):
        """Process HTML and return cleaned content and interactive elements"""
        cleaned = self.clean_html(html)
        truncated = self.truncate_html(cleaned)
        interactive = self.extract_interactive_elements(html)

        if self.print_to_console:
            self.logger.info("--- Processed HTML sent to LLM ---")
            self.logger.info(truncated)
            self.logger.info("--- End of Processed HTML ---")
        
        return {
            'html': truncated,
            'interactive_elements': interactive
        }