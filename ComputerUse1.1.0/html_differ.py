import re
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from logger import Logger

class HTMLDiffer:
    """Compares HTML between steps and identifies new/changed content"""
    
    def __init__(self):
        self.logger = Logger()
        self.previous_html = None
        self.previous_processed = None
        
    def normalize_html_for_comparison(self, html):
        """Normalize HTML for more accurate comparison"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove dynamic attributes that change frequently
            dynamic_attrs = ['style', 'data-reactid', 'data-react-checksum']
            for tag in soup.find_all(True):
                for attr in dynamic_attrs:
                    if attr in tag.attrs:
                        del tag.attrs[attr]
            
            # Normalize whitespace
            normalized = str(soup)
            normalized = re.sub(r'\s+', ' ', normalized)
            normalized = re.sub(r'>\s+<', '><', normalized)
            
            return normalized.strip()
        except Exception as e:
            self.logger.error(f"Error normalizing HTML: {e}")
            return html
    
    def extract_new_content(self, current_html, processed_current):
        """Extract only new or significantly changed content"""
        if self.previous_html is None:
            # First time - return everything
            self.previous_html = current_html
            self.previous_processed = processed_current
            return {
                'new_content': processed_current,
                'change_type': 'initial_load',
                'has_changes': True,
                'change_summary': 'Initial page load'
            }
        
        try:
            # Normalize both HTML versions for comparison
            current_normalized = self.normalize_html_for_comparison(current_html)
            previous_normalized = self.normalize_html_for_comparison(self.previous_html)
            
            # Check if there are significant changes
            similarity = SequenceMatcher(None, previous_normalized, current_normalized).ratio()
            
            if similarity > 0.95:
                # Very minor changes - might just be dynamic content updates
                return {
                    'new_content': self._extract_minimal_changes(processed_current),
                    'change_type': 'minimal_changes',
                    'has_changes': False,
                    'change_summary': f'Minimal changes detected (similarity: {similarity:.2%})'
                }
            
            # Significant changes detected - extract new content
            new_content = self._find_new_content_sections(current_html, self.previous_html)
            
            # Update stored HTML
            self.previous_html = current_html
            self.previous_processed = processed_current
            
            if new_content:
                return {
                    'new_content': new_content,
                    'change_type': 'new_content',
                    'has_changes': True,
                    'change_summary': f'New content detected (similarity: {similarity:.2%})'
                }
            else:
                # No new content found, but changes exist - return full processed
                return {
                    'new_content': processed_current,
                    'change_type': 'structural_changes', 
                    'has_changes': True,
                    'change_summary': f'Structural changes detected (similarity: {similarity:.2%})'
                }
                
        except Exception as e:
            self.logger.error(f"Error in HTML diffing: {e}")
            # Fallback to full content
            return {
                'new_content': processed_current,
                'change_type': 'error_fallback',
                'has_changes': True,
                'change_summary': f'Error in diffing: {str(e)}'
            }
    
    def _extract_minimal_changes(self, processed_current):
        """For minimal changes, return a very short summary"""
        # Return just the first 1000 characters as a summary
        return processed_current[:1000] + "..." if len(processed_current) > 1000 else processed_current
    
    def _find_new_content_sections(self, current_html, previous_html):
        """Find sections that are new or significantly changed"""
        try:
            current_soup = BeautifulSoup(current_html, 'html.parser')
            previous_soup = BeautifulSoup(previous_html, 'html.parser')
            
            # Look for new interactive elements
            new_elements = []
            
            # Find elements that weren't in the previous version
            current_interactive = current_soup.find_all(['button', 'input', 'select', 'a', 'form'])
            previous_interactive = previous_soup.find_all(['button', 'input', 'select', 'a', 'form'])
            
            # Create signatures for comparison
            def element_signature(elem):
                return f"{elem.name}_{elem.get('id', '')}_{elem.get('class', '')}_{elem.get_text(strip=True)[:50]}"
            
            previous_signatures = {element_signature(elem) for elem in previous_interactive}
            
            for elem in current_interactive:
                if element_signature(elem) not in previous_signatures:
                    new_elements.append(elem)
            
            # Look for new content sections (divs, sections with significant content)
            new_content_sections = []
            
            # Find sections that might contain new content (like dropdowns, modals)
            potential_new_sections = current_soup.find_all(['div', 'section', 'nav', 'ul', 'ol'], 
                                                         attrs={'class': re.compile(r'(dropdown|menu|modal|popup|panel|expanded|open)', re.I)})
            
            for section in potential_new_sections:
                section_text = section.get_text(strip=True)
                if len(section_text) > 20:  # Only sections with meaningful content
                    # Check if this section existed before
                    section_sig = f"{section.get('class', '')}_{section_text[:100]}"
                    
                    # Simple check - if we can't find similar content in previous HTML
                    if section_text not in previous_html:
                        new_content_sections.append(section)
            
            # Compile new content
            if new_elements or new_content_sections:
                new_content_html = ""
                
                if new_elements:
                    new_content_html += "<!-- NEW INTERACTIVE ELEMENTS -->\n"
                    for elem in new_elements[:10]:  # Limit to prevent overflow
                        new_content_html += str(elem) + "\n"
                
                if new_content_sections:
                    new_content_html += "<!-- NEW CONTENT SECTIONS -->\n"
                    for section in new_content_sections[:5]:  # Limit to prevent overflow
                        new_content_html += str(section) + "\n"
                
                return new_content_html
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding new content sections: {e}")
            return None
    
    def get_change_context(self, last_action):
        """Get context about what might have changed based on the last action"""
        if not last_action:
            return "No previous action context"
        
        action_type = last_action.get('action', '')
        target = last_action.get('target', '')
        
        context_hints = {
            'click': f"Last action was clicking on '{target}' - look for newly visible elements like dropdowns, modals, or expanded sections",
            'type': f"Last action was typing in '{target}' - look for search suggestions, autocomplete, or form validation messages",
            'navigate': f"Last action was navigation to '{target}' - this is a new page load",
            'scroll': "Last action was scrolling - look for newly visible content that was loaded dynamically"
        }
        
        return context_hints.get(action_type, f"Last action was '{action_type}' on '{target}'")
    
    def reset(self):
        """Reset the differ (useful for new sessions)"""
        self.previous_html = None
        self.previous_processed = None
        self.logger.info("HTML differ reset for new session")