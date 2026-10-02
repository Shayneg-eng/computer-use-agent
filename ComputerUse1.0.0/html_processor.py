import re
from bs4 import BeautifulSoup
from config import SYSTEM_CONFIG

class HTMLProcessor:
    """Processes HTML for LLM consumption, focusing on text and interactive elements"""
    
    def __init__(self):
        self.truncate_length = SYSTEM_CONFIG["html_truncate_length"]
    
    def clean_html(self, html):
        """Clean HTML to retain only text and interactive elements"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove non-essential elements
            for tag in soup(["script", "style", "noscript", "svg", "img"]):
                tag.decompose()
            
            # Keep only text-heavy and interactive tags
            essential_tags = ['button', 'input', 'textarea', 'form', 'a', 
                            'h1', 'h2', 'h3', 'p', 'span', 'div', 'li', 'ul',
                            'strong', 'b', 'i', 'em']
            
            # Keep essential attributes
            essential_attrs = ['id', 'class', 'href', 'type', 'name', 'value', 'placeholder', 'aria-label', 'role', 'title']
            
            for tag in soup.find_all():
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
            
            # Extract buttons
            for btn in soup.find_all(['button', 'input'], type=['button', 'submit']):
                text = btn.get_text(strip=True) or btn.get('value', '') or btn.get('aria-label', '') or btn.get('title', '')
                if text:
                    selector = self._generate_selector(btn)
                    if selector not in [el['selector'] for el in interactive_elements]:
                        interactive_elements.append({
                            'type': 'button',
                            'text': text,
                            'selector': selector
                        })
            
            # Extract links
            for link in soup.find_all('a', href=True):
                text = link.get_text(strip=True) or link.get('aria-label', '') or link.get('title', '')
                if text:
                    selector = self._generate_selector(link)
                    if selector not in [el['selector'] for el in interactive_elements]:
                        interactive_elements.append({
                            'type': 'link',
                            'text': text,
                            'href': link['href'],
                            'selector': selector
                        })
            
            # Extract input fields
            for inp in soup.find_all('input', type=['text', 'email', 'password', 'search', 'tel']):
                placeholder = inp.get('placeholder', '')
                name = inp.get('name', '')
                label = inp.get('aria-label', '')
                selector = self._generate_selector(inp)
                if selector not in [el['selector'] for el in interactive_elements]:
                    interactive_elements.append({
                        'type': 'input',
                        'placeholder': placeholder,
                        'name': name,
                        'label': label,
                        'selector': selector
                    })
            
            # Extract text areas
            for textarea in soup.find_all('textarea'):
                placeholder = textarea.get('placeholder', '')
                name = textarea.get('name', '')
                label = textarea.get('aria-label', '')
                selector = self._generate_selector(textarea)
                if selector not in [el['selector'] for el in interactive_elements]:
                    interactive_elements.append({
                        'type': 'textarea',
                        'placeholder': placeholder,
                        'name': name,
                        'label': label,
                        'selector': selector
                    })

            return interactive_elements
            
        except Exception as e:
            print(f"Error extracting interactive elements: {e}")
            return []
    
    def _generate_selector(self, element):
        """Generate a simple CSS selector"""
        if element.get('id'):
            return f"#{element['id']}"
        if element.get('class'):
            class_str = '.'.join(c for c in element['class'] if c and c.strip())
            return f"{element.name}.{class_str}"
        if element.get('name'):
            return f"{element.name}[name='{element['name']}']"
        if element.get('href'):
            return f"a[href='{element['href']}']"
        
        # Fallback to a more general selector
        selector = element.name
        
        # Add index if it's not unique
        siblings = element.find_previous_siblings(element.name)
        if siblings:
            index = len(siblings) + 1
            selector += f":nth-of-type({index})"
            
        return selector
    
    def process(self, html):
        """Process HTML and return cleaned content and interactive elements"""
        cleaned = self.clean_html(html)
        truncated = self.truncate_html(cleaned)
        interactive = self.extract_interactive_elements(html)
        
        return {
            'html': truncated,
            'interactive_elements': interactive
        }