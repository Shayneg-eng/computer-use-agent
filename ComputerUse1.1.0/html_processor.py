import re
from bs4 import BeautifulSoup
from config import SYSTEM_CONFIG
from logger import Logger

class HTMLProcessor:
    """Processes HTML for LLM consumption, focusing on user-actionable content and context"""
    
    def __init__(self):
        self.truncate_length = SYSTEM_CONFIG["html_truncate_length"]
        self.print_to_console = SYSTEM_CONFIG.get("print_html_to_console", False)
        self.logger = Logger()
        
        # Define content categories for intelligent filtering
        self.essential_interactive = ['button', 'input', 'textarea', 'select', 'option', 'a', 'form']
        self.contextual_content = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'label', 'legend', 'title']
        self.structural_content = ['nav', 'main', 'section', 'article', 'aside', 'header', 'footer']
        self.informational_content = ['p', 'span', 'div', 'li', 'ul', 'ol', 'dl', 'dt', 'dd']
        self.emphasis_content = ['strong', 'b', 'em', 'i', 'mark']
        
        # Patterns that suggest important content
        self.important_patterns = [
            r'\$\d+',  # prices
            r'\d+\.\d+.*star',  # ratings
            r'\d+:\d+\s*(am|pm|AM|PM)',  # times
            r'(available|unavailable|sold out|in stock)',  # availability
            r'\d+\s*(results?|items?|found)',  # result counts
            r'(page \d+ of \d+|showing \d+-\d+)',  # pagination info
            r'(selected|active|current)',  # current state
        ]
        
    def process_with_diff(self, html, html_differ, last_action=None):
        """Process HTML with diff awareness"""
        try:
            # Do normal processing first
            processed_data = self.process(html)
            
            # Get diff information
            diff_result = html_differ.extract_new_content(html, processed_data['html'])
            
            # Add diff context
            processed_data['diff_info'] = diff_result
            processed_data['change_context'] = html_differ.get_change_context(last_action)
            
            # If there are minimal changes, use the new content only
            if diff_result['change_type'] in ['minimal_changes', 'new_content']:
                processed_data['html_for_llm'] = diff_result['new_content']
            else:
                processed_data['html_for_llm'] = processed_data['html']
            
            return processed_data
            
        except Exception as e:
            self.logger.error(f"Error in process_with_diff: {e}")
            # Fallback to normal processing
            return self.process(html)
    
    def detect_page_type(self, soup):
        """Detect the type of page to apply appropriate filtering strategies"""
        # Search results page indicators
        if soup.find(attrs={"class": re.compile(r"search|results", re.I)}) or \
           soup.find(text=re.compile(r"\d+\s*(results?|matches?|found)", re.I)):
            return "search_results"
        
        # Form page indicators
        if len(soup.find_all("form")) > 0 or len(soup.find_all("input")) > 3:
            return "form"
        
        # Product/detail page indicators
        if soup.find(attrs={"class": re.compile(r"product|detail|item", re.I)}):
            return "product_detail"
        
        # Landing/home page indicators
        if soup.find(attrs={"class": re.compile(r"hero|banner|landing", re.I)}):
            return "landing"
        
        return "general"
    
    def is_important_text(self, text):
        """Check if text content contains important information"""
        if not text or len(text.strip()) < 2:
            return False
        
        text = text.strip().lower()
        
        # Check against important patterns
        for pattern in self.important_patterns:
            if re.search(pattern, text, re.I):
                return True
        
        # Check for navigation/action words
        action_words = ['search', 'filter', 'sort', 'view', 'select', 'choose', 'book', 'reserve', 
                       'add', 'remove', 'edit', 'save', 'cancel', 'submit', 'next', 'previous',
                       'sign in', 'log in', 'register', 'cart', 'checkout']
        
        return any(word in text for word in action_words)
    
    def should_keep_element(self, element, page_type):
        """Determine if an element should be kept based on its importance"""
        tag_name = element.name.lower() if element.name else ""
        
        # Always keep essential interactive elements
        if tag_name in self.essential_interactive:
            return True
        
        # Always keep contextual headers and labels
        if tag_name in self.contextual_content:
            return True
        
        # Keep structural elements that contain interactive content
        if tag_name in self.structural_content:
            if element.find_all(self.essential_interactive):
                return True
        
        # Check if element has important attributes
        important_attrs = ['id', 'name', 'role', 'aria-label', 'data-testid', 'onclick', 
                          'href', 'type', 'value', 'placeholder']
        if any(attr in element.attrs for attr in important_attrs):
            return True
        
        # Check if element contains important text
        text_content = element.get_text(strip=True)
        if self.is_important_text(text_content):
            return True
        
        # Keep elements with important CSS classes (likely interactive)
        class_list = element.get('class', [])
        important_class_patterns = [
            r'btn|button', r'link', r'menu', r'nav', r'search', r'filter',
            r'form', r'input', r'select', r'dropdown', r'modal', r'popup',
            r'card', r'item', r'result', r'product', r'price', r'rating'
        ]
        
        for class_name in class_list:
            for pattern in important_class_patterns:
                if re.search(pattern, class_name, re.I):
                    return True
        
        # For search results pages, be more liberal with content
        if page_type == "search_results":
            if tag_name in self.informational_content and len(text_content) > 5:
                return True
        
        return False
    
    def clean_html(self, html):
        """Intelligently clean HTML to retain user-actionable content and context"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            page_type = self.detect_page_type(soup)
            
            # Remove definitely unnecessary elements
            for tag in soup(["script", "style", "noscript", "meta", "link"]):
                tag.decompose()
            
            # Remove or simplify SVG and images but keep alt text
            for tag in soup.find_all(["svg", "img"]):
                alt_text = tag.get('alt', '')
                title_text = tag.get('title', '')
                if alt_text or title_text:
                    # Replace with span containing the descriptive text
                    replacement_text = alt_text or title_text
                    if self.is_important_text(replacement_text):
                        new_span = soup.new_tag("span", **{"class": "img-alt-text"})
                        new_span.string = f"[Image: {replacement_text}]"
                        tag.replace_with(new_span)
                    else:
                        tag.decompose()
                else:
                    tag.decompose()
            
            # Process all elements and decide what to keep
            all_elements = list(soup.find_all(True))
            
            for element in all_elements:
                if not self.should_keep_element(element, page_type):
                    # Don't remove the element if it contains important children
                    important_children = [child for child in element.find_all(True) 
                                        if self.should_keep_element(child, page_type)]
                    
                    if not important_children:
                        # Check if removing this element would lose important text
                        element_text = element.get_text(strip=True)
                        child_text = ' '.join([child.get_text(strip=True) 
                                             for child in element.children if hasattr(child, 'get_text')])
                        
                        unique_text = element_text.replace(child_text, '').strip()
                        
                        if unique_text and self.is_important_text(unique_text):
                            # Keep as text node
                            element.name = 'span'
                            element.attrs = {}
                        else:
                            # Unwrap to preserve children but remove the wrapper
                            element.unwrap()
            
            # Clean up attributes, keeping only essential ones
            essential_attrs = ['id', 'class', 'name', 'type', 'value', 'href', 'src', 
                             'placeholder', 'aria-label', 'role', 'title', 'onclick', 
                             'data-testid', 'for', 'action', 'method']
            
            for tag in soup.find_all(True):
                attrs_to_keep = {attr: value for attr, value in tag.attrs.items() 
                               if attr in essential_attrs}
                tag.attrs = attrs_to_keep
            
            # Clean whitespace but preserve structure
            cleaned_html = str(soup)
            cleaned_html = re.sub(r'\n\s*\n', '\n', cleaned_html)  # Remove empty lines
            cleaned_html = re.sub(r'[ \t]+', ' ', cleaned_html)     # Normalize spaces
            
            return cleaned_html.strip()
            
        except Exception as e:
            self.logger.error(f"Error cleaning HTML: {e}")
            return html
    
    def smart_truncate_html(self, html, page_type="general"):
        """Smart truncation that preserves complete semantic sections"""
        if len(html) <= self.truncate_length:
            return html
        
        # Try to find good break points
        soup = BeautifulSoup(html, 'html.parser')
        
        # For search results, try to keep complete result items
        if page_type == "search_results":
            return self._truncate_search_results(soup)
        
        # For forms, prioritize keeping the form complete
        if page_type == "form":
            return self._truncate_form_content(soup)
        
        # General truncation - find the last complete element within limit
        html_str = str(soup)
        if len(html_str) <= self.truncate_length:
            return html_str
        
        truncated = html_str[:self.truncate_length]
        
        # Find the last complete tag
        last_close_tag = truncated.rfind('>')
        last_open_tag = truncated.rfind('<')
        
        if last_close_tag > last_open_tag and last_close_tag > self.truncate_length * 0.7:
            truncated = html_str[:last_close_tag + 1]
        else:
            # Find last complete word
            last_space = truncated.rfind(' ')
            if last_space > self.truncate_length * 0.8:
                truncated = html_str[:last_space]
        
        return truncated + "\n<!-- [Content truncated for length] -->"
    
    def _truncate_search_results(self, soup):
        """Truncate search results while keeping complete result items"""
        # Keep header/navigation elements
        preserved_elements = []
        
        # Find result containers
        result_patterns = [
            soup.find_all(attrs={"class": re.compile(r"result|item|card|product", re.I)}),
            soup.find_all("li"),  # Often used for results
            soup.find_all("article"),  # Semantic result containers
        ]
        
        result_items = []
        for pattern in result_patterns:
            if pattern:
                result_items = pattern
                break
        
        if not result_items:
            # Fall back to general truncation
            return str(soup)[:self.truncate_length] + "\n<!-- [Content truncated] -->"
        
        # Keep adding complete result items until we approach the limit
        current_html = ""
        items_kept = 0
        
        # Keep non-result content first (navigation, filters, etc.)
        non_result_content = str(soup)
        for item in result_items:
            non_result_content = non_result_content.replace(str(item), "")
        
        current_html += non_result_content
        
        for item in result_items:
            item_html = str(item)
            if len(current_html + item_html) > self.truncate_length * 0.9:
                break
            current_html += item_html
            items_kept += 1
        
        if items_kept < len(result_items):
            current_html += f"\n<!-- [Showing {items_kept} of {len(result_items)} results - content truncated] -->"
        
        return current_html
    
    def _truncate_form_content(self, soup):
        """Truncate form content while preserving form structure"""
        # Keep all form elements
        forms = soup.find_all("form")
        essential_html = ""
        
        for form in forms:
            essential_html += str(form)
        
        if len(essential_html) <= self.truncate_length:
            return str(soup)
        
        # If forms are too long, prioritize inputs and labels
        inputs_and_labels = soup.find_all(["input", "textarea", "select", "button", "label"])
        truncated_content = ""
        
        for element in inputs_and_labels:
            element_str = str(element)
            if len(truncated_content + element_str) > self.truncate_length * 0.9:
                break
            truncated_content += element_str
        
        return truncated_content + "\n<!-- [Form content truncated] -->"
    
    def extract_interactive_elements(self, html):
        """Extract interactive elements with enhanced context and grouping"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            interactive_elements = []
            page_type = self.detect_page_type(soup)
            
            # Enhanced interactive element detection
            interactive_selectors = [
                ('form', self._extract_form_elements),
                ('input', self._extract_input_elements),
                ('button', self._extract_button_elements),
                ('a', self._extract_link_elements),
                ('[onclick]', self._extract_clickable_elements),
                ('[role="button"]', self._extract_role_button_elements),
                ('select', self._extract_select_elements),
                ('textarea', self._extract_textarea_elements),
            ]
            
            processed_elements = set()
            
            for selector, extractor in interactive_selectors:
                # Handle None selectors safely - FIX APPLIED HERE
                if not selector or selector is None:
                    self.logger.debug(f"Skipping None selector")
                    continue
                    
                try:
                    # Check if selector is a CSS selector or tag name
                    if selector.startswith('[') or selector.startswith('.') or selector.startswith('#'):
                        elements = soup.select(selector)
                    else:
                        elements = soup.find_all(selector)
                    
                    for element in elements:
                        element_id = id(element)
                        if element_id in processed_elements:
                            continue
                        
                        try:
                            extracted = extractor(element, soup, page_type)
                            if extracted:
                                interactive_elements.extend(extracted if isinstance(extracted, list) else [extracted])
                                processed_elements.add(element_id)
                        except Exception as extractor_error:
                            self.logger.debug(f"Extractor {extractor.__name__} failed for element: {extractor_error}")
                            continue
                            
                except Exception as selector_error:
                    self.logger.debug(f"Selector {selector} failed: {selector_error}")
                    continue
            
            # Group related elements
            grouped_elements = self._group_related_elements(interactive_elements)
            
            return grouped_elements
            
        except Exception as e:
            self.logger.error(f"Error extracting interactive elements: {e}")
            return []
    
    def _extract_form_elements(self, form, soup, page_type):
        """Extract form with all its elements as a group"""
        form_data = {
            'type': 'form',
            'action': form.get('action', ''),
            'method': form.get('method', 'GET'),
            'selector': self._generate_enhanced_selector(form),
            'elements': []
        }
        
        # Find all form controls within this form
        controls = form.find_all(['input', 'textarea', 'select', 'button'])
        for control in controls:
            control_data = self._extract_form_control(control)
            if control_data:
                form_data['elements'].append(control_data)
        
        return [form_data] if form_data['elements'] else None
    
    def _extract_input_elements(self, input_elem, soup, page_type):
        """Extract input elements with enhanced context"""
        input_type = input_elem.get('type', 'text')
        
        # Skip inputs that are part of forms (handled separately)
        if input_elem.find_parent('form'):
            return None
        
        return {
            'type': f'input_{input_type}',
            'name': input_elem.get('name', ''),
            'placeholder': input_elem.get('placeholder', ''),
            'value': input_elem.get('value', ''),
            'label': self._get_enhanced_label(input_elem),
            'selector': self._generate_enhanced_selector(input_elem),
            'required': input_elem.has_attr('required'),
            'context': self._get_element_context(input_elem)
        }
    
    def _extract_button_elements(self, button, soup, page_type):
        """Extract button elements with context"""
        return {
            'type': 'button',
            'text': button.get_text(strip=True) or button.get('value', ''),
            'button_type': button.get('type', 'button'),
            'selector': self._generate_enhanced_selector(button),
            'context': self._get_element_context(button),
            'form_associated': button.find_parent('form') is not None
        }
    
    def _extract_link_elements(self, link, soup, page_type):
        """Extract link elements with enhanced context"""
        href = link.get('href', '')
        if not href or href.startswith('javascript:') or href == '#':
            return None
        
        return {
            'type': 'link',
            'text': link.get_text(strip=True),
            'href': href,
            'selector': self._generate_enhanced_selector(link),
            'context': self._get_element_context(link),
            'is_external': href.startswith('http') and not href.startswith(soup.find('base', href=True))
        }
    
    def _extract_clickable_elements(self, element, soup, page_type):
        """Extract elements with click handlers"""
        return {
            'type': 'clickable',
            'text': element.get_text(strip=True),
            'tag': element.name,
            'selector': self._generate_enhanced_selector(element),
            'onclick': element.get('onclick', ''),
            'context': self._get_element_context(element)
        }
    
    def _extract_role_button_elements(self, element, soup, page_type):
        """Extract elements with button role"""
        return {
            'type': 'role_button',
            'text': element.get_text(strip=True),
            'tag': element.name,
            'selector': self._generate_enhanced_selector(element),
            'context': self._get_element_context(element)
        }
    
    def _extract_select_elements(self, select, soup, page_type):
        """Extract select elements with options"""
        options = [{'value': opt.get('value', ''), 'text': opt.get_text(strip=True)} 
                  for opt in select.find_all('option')]
        
        return {
            'type': 'select',
            'name': select.get('name', ''),
            'label': self._get_enhanced_label(select),
            'selector': self._generate_enhanced_selector(select),
            'options': options[:10],  # Limit to first 10 options
            'total_options': len(options),
            'context': self._get_element_context(select)
        }
    
    def _extract_textarea_elements(self, textarea, soup, page_type):
        """Extract textarea elements"""
        return {
            'type': 'textarea',
            'name': textarea.get('name', ''),
            'placeholder': textarea.get('placeholder', ''),
            'label': self._get_enhanced_label(textarea),
            'selector': self._generate_enhanced_selector(textarea),
            'context': self._get_element_context(textarea)
        }
    
    def _extract_form_control(self, control):
        """Extract individual form control data"""
        control_type = control.name
        data = {
            'tag': control_type,
            'type': control.get('type') if control_type == 'input' else control_type,
            'name': control.get('name', ''),
            'selector': self._generate_enhanced_selector(control)
        }
        
        if control_type == 'input':
            data.update({
                'placeholder': control.get('placeholder', ''),
                'value': control.get('value', ''),
                'required': control.has_attr('required')
            })
        elif control_type == 'textarea':
            data['placeholder'] = control.get('placeholder', '')
        elif control_type == 'select':
            options = [opt.get_text(strip=True) for opt in control.find_all('option')]
            data['options'] = options[:5]  # First 5 options
        elif control_type == 'button':
            data['text'] = control.get_text(strip=True) or control.get('value', '')
        
        data['label'] = self._get_enhanced_label(control)
        return data
    
    def _get_enhanced_label(self, element):
        """Get label with multiple fallback strategies"""
        # Strategy 1: Explicit label with 'for' attribute
        if element.get('id'):
            label = element.find_previous_sibling('label', attrs={'for': element['id']})
            if not label:
                label = element.find_parent().find('label', attrs={'for': element['id']})
            if label:
                return label.get_text(strip=True)
        
        # Strategy 2: Parent label
        parent_label = element.find_parent('label')
        if parent_label:
            label_text = parent_label.get_text(strip=True)
            element_text = element.get_text(strip=True)
            return label_text.replace(element_text, '').strip()
        
        # Strategy 3: Nearby text (common pattern)
        previous_sibling = element.find_previous_sibling(string=True)
        if previous_sibling and previous_sibling.strip():
            return previous_sibling.strip()
        
        # Strategy 4: Aria-label or title
        return element.get('aria-label', '') or element.get('title', '') or element.get('placeholder', '')
    
    def _get_element_context(self, element):
        """Get contextual information about element's location and purpose"""
        context = {}
        
        # Parent container context
        parent_classes = []
        current = element.parent
        depth = 0
        while current and depth < 3:
            if hasattr(current, 'get') and current.get('class'):
                parent_classes.extend(current.get('class'))
            current = current.parent
            depth += 1
        
        if parent_classes:
            context['container_classes'] = parent_classes[:5]  # Limit to 5 classes
        
        # Nearby text content
        nearby_text = []
        for sibling in element.find_previous_siblings(string=True):
            text = sibling.strip()
            if text and len(text) < 100:
                nearby_text.append(text)
            if len(nearby_text) >= 2:
                break
        
        if nearby_text:
            context['nearby_text'] = nearby_text
        
        return context
    
    def _generate_enhanced_selector(self, element):
        """Generate multiple selector options ranked by reliability"""
        selectors = []
        
        # ID selector (most reliable)
        element_id = element.get('id')
        if element_id:
            selectors.append({'selector': f"#{element_id}", 'reliability': 'high'})
        
        # Name attribute (good for forms)
        element_name = element.get('name')
        if element_name:
            name_selector = f"{element.name}[name='{element_name}']"
            element_type = element.get('type')
            if element_type:
                name_selector += f"[type='{element_type}']"
            selectors.append({'selector': name_selector, 'reliability': 'high'})
        
        # Data attributes (usually stable)
        for attr in element.attrs:
            if attr and attr.startswith('data-'):  # Add safety check for attr
                value = element[attr]
                if isinstance(value, list):
                    value = ' '.join(str(v) for v in value)
                elif value is not None:
                    value = str(value)
                else:
                    continue
                selectors.append({'selector': f"[{attr}='{value}']", 'reliability': 'medium'})
        
        # Aria-label (semantic)
        aria_label = element.get('aria-label')
        if aria_label:
            label = str(aria_label)[:30]  # Truncate long labels
            selectors.append({'selector': f"[aria-label*='{label}']", 'reliability': 'medium'})
        
        # Class-based (less reliable but useful)
        classes = element.get('class', [])
        if classes:
            stable_classes = []
            for cls in classes:
                if cls and len(str(cls)) > 2 and not re.match(r'^[a-zA-Z]{1,3}[0-9]+', str(cls)):
                    stable_classes.append(str(cls))
            
            if stable_classes:
                class_selector = f"{element.name}.{'.'.join(stable_classes[:2])}"
                selectors.append({'selector': class_selector, 'reliability': 'medium'})
        
        # Fallback: tag with attributes
        if not selectors:
            attrs = []
            for attr in ['type', 'role']:
                attr_value = element.get(attr)
                if attr_value:
                    attrs.append(f"[{attr}='{attr_value}']")
            fallback = element.name + ''.join(attrs)
            selectors.append({'selector': fallback, 'reliability': 'low'})
        
        return selectors[0]['selector'] if selectors else element.name
    
    def _group_related_elements(self, elements):
        """Group related interactive elements together"""
        # This is a simplified grouping - could be enhanced further
        groups = []
        form_elements = []
        search_elements = []
        navigation_elements = []
        other_elements = []
        
        for element in elements:
            element_type = element.get('type', '')
            
            if 'form' in element_type or element.get('form_associated'):
                form_elements.append(element)
            elif 'search' in str(element).lower():
                search_elements.append(element)
            elif 'nav' in str(element).lower() or element_type == 'link':
                navigation_elements.append(element)
            else:
                other_elements.append(element)
        
        # Create groups
        if form_elements:
            groups.append({'group_type': 'forms', 'elements': form_elements})
        if search_elements:
            groups.append({'group_type': 'search', 'elements': search_elements})
        if navigation_elements:
            groups.append({'group_type': 'navigation', 'elements': navigation_elements})
        if other_elements:
            groups.append({'group_type': 'other_interactive', 'elements': other_elements})
        
        return groups if groups else elements
    
    def process(self, html):
        """Process HTML with enhanced intelligence and return structured data"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            page_type = self.detect_page_type(soup)
            
            cleaned = self.clean_html(html)
            truncated = self.smart_truncate_html(cleaned, page_type)
            interactive = self.extract_interactive_elements(html)
            
            # Extract page metadata
            page_info = self._extract_page_info(soup)
            
            if self.print_to_console:
                self.logger.info("--- Enhanced HTML Processing Results ---")
                self.logger.info(f"Page Type: {page_type}")
                self.logger.info(f"Page Title: {page_info.get('title', 'Not found')}")
                self.logger.info(f"Interactive Elements Found: {len(interactive)}")
                self.logger.info("--- Processed HTML ---")
                self.logger.info(truncated[:1000] + "..." if len(truncated) > 1000 else truncated)
                self.logger.info("--- End Processing Results ---")
            
            return {
                'html': truncated,
                'interactive_elements': interactive,
                'page_type': page_type,
                'page_info': page_info,
                'processing_stats': {
                    'original_length': len(html),
                    'processed_length': len(truncated),
                    'interactive_count': len(interactive)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error in HTML processing: {e}")
            # Fallback to basic processing
            return {
                'html': html[:self.truncate_length],
                'interactive_elements': [],
                'page_type': 'unknown',
                'page_info': {},
                'processing_stats': {'error': str(e)}
            }
    
    def _extract_page_info(self, soup):
        """Extract basic page information"""
        info = {}
        
        # Title
        title_elem = soup.find('title') or soup.find('h1')
        if title_elem:
            info['title'] = title_elem.get_text(strip=True)
        
        # Description
        desc_meta = soup.find('meta', attrs={'name': 'description'})
        if desc_meta:
            info['description'] = desc_meta.get('content', '')
        
        # Current URL (if available in links)
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        if canonical:
            info['canonical_url'] = canonical.get('href', '')
        
        # Count key elements
        info['counts'] = {
            'forms': len(soup.find_all('form')),
            'inputs': len(soup.find_all('input')),
            'buttons': len(soup.find_all('button')),
            'links': len(soup.find_all('a', href=True))
        }
        
        return info