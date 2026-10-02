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
    
    async def _click(self, selector):
        """Click on an element"""
        try:
            # Wait for element to be visible
            await self.page.wait_for_selector(selector, timeout=self.timeout)
            await self.page.click(selector, timeout=self.timeout)
            
            # Wait a moment for the page to respond
            await asyncio.sleep(1)
            
            return {"success": True, "message": f"Clicked on {selector}"}
        except TimeoutError:
            return {"success": False, "error": f"Element not found or not clickable: {selector}"}
        except Exception as e:
            return {"success": False, "error": f"Click failed: {str(e)}"}
    
    async def _navigate(self, url):
        """Navigate to a URL"""
        try:
            # Add protocol if missing
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            await self.page.goto(url, timeout=self.timeout)
            
            # Wait for page to load
            await self.page.wait_for_load_state('networkidle', timeout=self.timeout)
            
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