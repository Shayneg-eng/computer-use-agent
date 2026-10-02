import asyncio
import json
from playwright.async_api import TimeoutError
from config import BROWSER_CONFIG, SUPPORTED_ACTIONS
from logger import Logger

class ActionExecutor:
    """Executes browser actions based on LLM responses"""
    
    def __init__(self, page):
        self.page = page
        self.timeout = BROWSER_CONFIG["timeout"]
        self.logger = Logger()
    
    async def execute_action(self, action_data):
        """Execute a single action based on the action data"""
        try:
            action_type = action_data.get("action")
            target = action_data.get("target")
            text = action_data.get("text", "")
            
            if action_type not in SUPPORTED_ACTIONS:
                raise ValueError(f"Unsupported action: {action_type}")
            
            print(f"Executing action: {action_type} on target: {target}")
            
            if action_type == "click":
                return await self._click(target)
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
                return {"success": True, "message": "No action taken"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def click_google_search_button(self):
        """
        More robust method to click Google search button with fallback selectors
        """
        # List of possible selectors for Google search button, in order of preference
        search_button_selectors = [
            # Standard Google search button selectors
            "input[name='btnK'][type='submit']",  # Most reliable - by name and type
            "input[value='Google Search']",       # By value attribute
            "button[aria-label*='Search']",       # Search button with aria-label
            "input[type='submit'][value*='Search']",  # Any submit input with "Search" in value
            
            # Alternative approaches
            "form[role='search'] input[type='submit']",  # Submit button within search form
            "div.FPdoLc input[type='submit']",    # Within specific Google container
            "center input[type='submit']",        # Often centered on page
            
            # Fallback to any submit button (risky but sometimes necessary)
            "input[type='submit']"
        ]
        
        for selector in search_button_selectors:
            try:
                # Wait for element to exist
                await self.page.wait_for_selector(selector, timeout=2000)
                
                # Check if element is visible and enabled
                element = await self.page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    is_enabled = await element.is_enabled()
                    
                    if is_visible and is_enabled:
                        print(f"Found search button with selector: {selector}")
                        await element.click()
                        await asyncio.sleep(1)  # Wait for search to initiate
                        return {"success": True, "message": f"Clicked search button: {selector}"}
                        
            except Exception as e:
                print(f"Selector {selector} failed: {e}")
                continue
        
        # If all selectors fail, try alternative approach
        return await self.alternative_search_approach()

    async def alternative_search_approach(self):
        """
        Alternative approach: submit search via Enter key or form submission
        """
        try:
            # Method 1: Press Enter in the search box
            search_input_selectors = [
                "input[name='q']",
                "textarea[name='q']", 
                "input[type='search']",
                "input[title*='Search']"
            ]
            
            for selector in search_input_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        await element.focus()
                        await self.page.keyboard.press('Enter')
                        await asyncio.sleep(1)
                        return {"success": True, "message": "Submitted search via Enter key"}
                except:
                    continue
            
            # Method 2: Try to submit the form directly
            search_forms = await self.page.query_selector_all("form")
            for form in search_forms:
                try:
                    # Check if this form contains a search input
                    search_input = await form.query_selector("input[name='q'], textarea[name='q']")
                    if search_input:
                        await form.evaluate("form => form.submit()")
                        await asyncio.sleep(1)
                        return {"success": True, "message": "Submitted search form directly"}
                except:
                    continue
                    
            return {"success": False, "error": "Could not find any way to submit search"}
            
        except Exception as e:
            return {"success": False, "error": f"Alternative search failed: {str(e)}"}
        
    async def _handle_dropdown_selection(self, selector):
        """Handle dropdown option selection with multiple strategies"""
        try:
            # Parse the selector to get select and option parts
            parts = selector.split(' option[')
            if len(parts) != 2:
                return {"success": False, "error": f"Invalid dropdown selector format: {selector}"}
            
            select_selector = parts[0]
            option_part = parts[1].rstrip(']')
            
            # Extract the value from option selector
            if 'value=' in option_part:
                value = option_part.split("value='")[1].split("'")[0]
            else:
                return {"success": False, "error": f"Could not extract value from: {option_part}"}
            
            # Strategy 1: Use Playwright's selectOption method
            try:
                await self.page.wait_for_selector(select_selector, timeout=5000)
                await self.page.select_option(select_selector, value=value)
                await asyncio.sleep(1)
                return {"success": True, "message": f"Selected option {value} in dropdown {select_selector}"}
            except Exception as e:
                print(f"Strategy 1 (selectOption) failed: {e}")
            
            # Strategy 2: Click the select then click the option
            try:
                await self.page.click(select_selector)
                await asyncio.sleep(0.5)  # Wait for dropdown to open
                
                # Try to click the specific option
                option_selector = f"{select_selector} option[value='{value}']"
                await self.page.wait_for_selector(option_selector, timeout=2000)
                await self.page.click(option_selector)
                await asyncio.sleep(1)
                return {"success": True, "message": f"Clicked option {value} in dropdown {select_selector}"}
            except Exception as e:
                print(f"Strategy 2 (click option) failed: {e}")
            
            # Strategy 3: Use keyboard navigation
            try:
                await self.page.focus(select_selector)
                # Send the value directly (works for some dropdowns)
                await self.page.keyboard.type(value)
                await self.page.keyboard.press('Enter')
                await asyncio.sleep(1)
                return {"success": True, "message": f"Set dropdown value using keyboard: {value}"}
            except Exception as e:
                print(f"Strategy 3 (keyboard) failed: {e}")
            
            return {"success": False, "error": f"All dropdown selection strategies failed for {selector}"}
            
        except Exception as e:
            return {"success": False, "error": f"Dropdown selection failed: {str(e)}"}

    async def _handle_select_dropdown(self, selector):
        """Handle clicking on select dropdown to open it"""
        try:
            await self.page.wait_for_selector(selector, timeout=self.timeout)
            
            # First check if it's already opened (has focus or expanded state)
            element = await self.page.query_selector(selector)
            if element:
                is_expanded = await element.get_attribute('aria-expanded')
                if is_expanded == 'true':
                    return {"success": True, "message": f"Dropdown {selector} is already open"}
            
            # Click to open the dropdown
            await self.page.click(selector)
            await asyncio.sleep(1)  # Wait for dropdown to animate open
            
            return {"success": True, "message": f"Opened dropdown {selector}"}
            
        except Exception as e:
            return {"success": False, "error": f"Failed to open dropdown {selector}: {str(e)}"}
    
    async def _click(self, selector):
        """Enhanced click method with special handling for dropdowns and fallback strategies"""
        try:
            # Special case for Google search button
            if ('btnK' in selector or 'Google Search' in selector or 
                ('gNO89b' in selector and 'submit' in selector)):
                return await self.click_google_search_button()
            
            # Special case for dropdown selections (select option pattern)
            if ' option[' in selector:
                return await self._handle_dropdown_selection(selector)
            
            # Special case for select dropdowns
            if selector.startswith('select#') and 'option' not in selector:
                return await self._handle_select_dropdown(selector)
            
            # Try the original selector first
            await self.page.wait_for_selector(selector, timeout=self.timeout)
            await self.page.click(selector, timeout=self.timeout)
            
            # Wait a moment for the page to respond
            await asyncio.sleep(1)
            
            return {"success": True, "message": f"Clicked on {selector}"}
            
        except TimeoutError:
            # Try fallback strategies for common elements
            fallback_result = await self._try_fallback_click(selector)
            if fallback_result["success"]:
                return fallback_result
            
            return {"success": False, "error": f"Element not found or not clickable: {selector}"}
        except Exception as e:
            return {"success": False, "error": f"Click failed: {str(e)}"}
            
        except TimeoutError:
            # Try fallback strategies for common elements
            fallback_result = await self._try_fallback_click(selector)
            if fallback_result["success"]:
                return fallback_result
            
            return {"success": False, "error": f"Element not found or not clickable: {selector}"}
        except Exception as e:
            return {"success": False, "error": f"Click failed: {str(e)}"}
    
    async def _try_fallback_click(self, original_selector):
        """Try alternative selectors when the original fails"""
        fallback_strategies = []
        
        # If selector contains dynamic classes, try without them
        if '.' in original_selector and '[' in original_selector:
            # Extract just the attribute-based parts
            parts = original_selector.split('[')
            if len(parts) > 1:
                attribute_selector = '['.join([''] + parts[1:])  # Keep all [...] parts
                fallback_strategies.append(f"*{attribute_selector}")
        
        # Common fallback patterns
        if 'input' in original_selector and 'submit' in original_selector:
            fallback_strategies.extend([
                "input[type='submit']",
                "button[type='submit']",
                "input[name='btnK']"
            ])
        
        if 'button' in original_selector:
            fallback_strategies.extend([
                "button",
                "[role='button']"
            ])
        
        # Try each fallback
        for fallback_selector in fallback_strategies:
            try:
                await self.page.wait_for_selector(fallback_selector, timeout=2000)
                await self.page.click(fallback_selector, timeout=2000)
                await asyncio.sleep(1)
                return {"success": True, "message": f"Clicked using fallback selector: {fallback_selector}"}
            except:
                continue
        
        return {"success": False, "error": "All fallback strategies failed"}
    
    async def _navigate(self, url):
        """Navigate to a URL"""
        try:
            # Add protocol if missing
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # Use 'domcontentloaded' to avoid issues with modern, always-loading sites
            await self.page.goto(url, timeout=self.timeout, wait_until='domcontentloaded')
            
            # The redundant wait_for_load_state('networkidle') call has been removed.
            
            return {"success": True, "message": f"Navigated to {url}"}
        except Exception as e:
            return {"success": False, "error": f"Navigation failed: {str(e)}"}
        
    async def _type(self, selector, text):
        """Type text into an input field"""
        try:
            await self.page.wait_for_selector(selector, timeout=self.timeout)
            
            # Clear existing text first
            await self.page.fill(selector, "")
            
            # Type new text
            await self.page.type(selector, text, delay=50)  # Small delay between keystrokes
            
            return {"success": True, "message": f"Typed '{text}' into {selector}"}
        except Exception as e:
            return {"success": False, "error": f"Type failed: {str(e)}"}
    
    async def _scroll(self, direction):
        """Scroll the page"""
        try:
            if direction == "up":
                await self.page.keyboard.press("PageUp")
            elif direction == "down":
                await self.page.keyboard.press("PageDown")
            elif direction == "top":
                await self.page.keyboard.press("Home")
            elif direction == "bottom":
                await self.page.keyboard.press("End")
            else:
                return {"success": False, "error": f"Invalid scroll direction: {direction}"}
            
            # Wait for scroll to complete
            await asyncio.sleep(0.5)
            
            return {"success": True, "message": f"Scrolled {direction}"}
        except Exception as e:
            return {"success": False, "error": f"Scroll failed: {str(e)}"}
    
    async def _wait(self, seconds):
        """Wait for a specified number of seconds"""
        try:
            wait_time = float(seconds)
            if wait_time > 30:  # Safety limit
                wait_time = 30
            
            await asyncio.sleep(wait_time)
            return {"success": True, "message": f"Waited {wait_time} seconds"}
        except Exception as e:
            return {"success": False, "error": f"Wait failed: {str(e)}"}

    def _ask(self, text):
        """Ask the user a question via the terminal"""
        if not text:
            return {"success": False, "error": "The 'ask' action requires a 'text' field."}
        self.logger.info(f"AI asks: {text}")
        return {"success": True, "message": f"Asked user: {text}"}

    def _tell(self, text):
        """Tell the user a message via the terminal"""
        if not text:
            return {"success": False, "error": "The 'tell' action requires a 'text' field."}
        self.logger.info(f"AI tells: {text}")
        return {"success": True, "message": f"Told user: {text}"}
    
    async def take_screenshot(self, path="screenshot.png"):
        """Take a screenshot of the current page"""
        try:
            await self.page.screenshot(path=path, full_page=True)
            return {"success": True, "message": f"Screenshot saved to {path}"}
        except Exception as e:
            return {"success": False, "error": f"Screenshot failed: {str(e)}"}
    
    def validate_action(self, action_data):
        """Validate action data structure"""
        if not isinstance(action_data, dict):
            return False, "Action data must be a dictionary"
        
        if "action" not in action_data:
            return False, "Missing 'action' field"
        
        action_type = action_data["action"]
        if action_type not in SUPPORTED_ACTIONS:
            return False, f"Unsupported action: {action_type}"
        
        # Validate required fields for each action type
        if action_type in ["click", "type"] and not action_data.get("target"):
            return False, f"Action '{action_type}' requires 'target' field"
        
        if action_type == "type" and not action_data.get("text"):
            return False, "Action 'type' requires 'text' field"
        
        if action_type == "navigate" and not action_data.get("target"):
            return False, "Action 'navigate' requires 'target' field"
        
        if action_type in ["ask", "tell"] and not action_data.get("text"):
            return False, f"Action '{action_type}' requires 'text' field"
        
        return True, "Valid action"