#!/usr/bin/env python3
"""
Computer Use AI - Main Application
A modular AI system that can control web browsers to complete tasks.
"""

import asyncio
import sys
import random
import json
from datetime import datetime
from playwright.async_api import async_playwright

# Import our modules
from config import BROWSER_CONFIG, SYSTEM_CONFIG, DEFAULT_TASK, START_URL
from html_processor import HTMLProcessor
from html_differ import HTMLDiffer
from actions import ActionExecutor
from llm_client import LLMClient
from logger import Logger

class ComputerUseAI:
    """Main class for the Computer Use AI system"""
    
    def __init__(self):
        self.logger = Logger()
        self.html_processor = HTMLProcessor()
        self.html_differ = HTMLDiffer()  # Add this line
        self.llm_client = LLMClient()
        self.action_executor = None
        self.browser = None
        self.page = None
        self.history = []
        
    def debug_llm_response(self, raw_response, step_number):
        """Debug helper to analyze LLM responses"""
        print(f"\n=== LLM RESPONSE DEBUG - STEP {step_number} ===")
        print(f"Response type: {type(raw_response)}")
        print(f"Response length: {len(raw_response) if raw_response else 0}")
        print(f"First 200 chars: {repr(raw_response[:200]) if raw_response else 'None'}")
        print(f"Last 100 chars: {repr(raw_response[-100:]) if raw_response and len(raw_response) > 100 else 'N/A'}")
        
        # Check for common issues
        if raw_response:
            if raw_response.startswith('\n'):
                print("⚠️  Response starts with newline")
            if not raw_response.strip().startswith('{'):
                print("⚠️  Response doesn't start with opening brace")
            if not raw_response.strip().endswith('}'):
                print("⚠️  Response doesn't end with closing brace")
            
            # Count braces
            open_braces = raw_response.count('{')
            close_braces = raw_response.count('}')
            print(f"Brace count: {open_braces} open, {close_braces} close")
            
        print("=" * 50)
    
    async def initialize_browser(self):
        """Initialize the browser and page with anti-detection measures"""
        try:
            playwright = await async_playwright().start()
            
            # Launch browser with anti-detection settings
            self.browser = await playwright.chromium.launch(
                headless=BROWSER_CONFIG["headless"],
                args=[
                    '--no-blink-features=AutomationControlled',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox'
                ]
            )
            
            # Create context with anti-detection settings
            context = await self.browser.new_context(
                viewport=BROWSER_CONFIG["viewport"],
                user_agent=BROWSER_CONFIG["user_agent"],
                locale=BROWSER_CONFIG["locale"],
                timezone_id=BROWSER_CONFIG["timezone_id"],
                extra_http_headers=BROWSER_CONFIG["extra_http_headers"]
            )
            
            # Create new page
            self.page = await context.new_page()
            
            # Remove webdriver property
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            # Mock plugins and permissions
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: async () => ({ state: 'granted' }),
                    }),
                });
            """)
            
            # Initialize action executor with the page
            self.action_executor = ActionExecutor(self.page)
            
            self.logger.info("Browser initialized successfully with anti-detection measures")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize browser: {e}")
            return False
    
    async def human_like_delay(self):
        """Add random delay to mimic human behavior"""
        if SYSTEM_CONFIG.get("human_like_delays", False):
            delay = random.uniform(
                SYSTEM_CONFIG.get("min_delay", 1),
                SYSTEM_CONFIG.get("max_delay", 3)
            )
            self.logger.debug(f"Human-like delay: {delay:.2f} seconds")
            await asyncio.sleep(delay)
    
    async def detect_captcha(self, html):
        """Detect if current page contains a CAPTCHA with more precision"""
        # More specific CAPTCHA patterns that are less likely to false positive
        captcha_patterns = [
            'g-recaptcha',
            'h-captcha',
            'cf-challenge',
            'captcha-container',
            'recaptcha-checkbox',
            'data-sitekey',
            'captcha-image',
            'captcha-input',
            'verify you are human',
            'prove you are not a robot'
        ]
        
        html_lower = html.lower()
        
        # Check for specific patterns
        detected_patterns = []
        for pattern in captcha_patterns:
            if pattern in html_lower:
                detected_patterns.append(pattern)
        
        # Also check page title and URL for CAPTCHA indicators
        try:
            page_title = await self.page.title()
            page_url = self.page.url
            
            title_indicators = ['captcha', 'verify', 'challenge', 'robot check']
            url_indicators = ['captcha', 'challenge', 'verify']
            
            for indicator in title_indicators:
                if indicator in page_title.lower():
                    detected_patterns.append(f"title:{indicator}")
            
            for indicator in url_indicators:
                if indicator in page_url.lower():
                    detected_patterns.append(f"url:{indicator}")
                    
        except Exception as e:
            self.logger.debug(f"Could not check page title/URL: {e}")
        
        if detected_patterns:
            self.logger.warning(f"CAPTCHA patterns detected: {detected_patterns}")
            return True
        
        return False
    
    async def wait_for_page_stability(self, timeout=5000):
        """Wait for page to stabilize after an action"""
        try:
            # Wait for network to be idle
            await self.page.wait_for_load_state('networkidle', timeout=timeout)
            
            # Additional small delay for dynamic content
            await asyncio.sleep(1)
            
            self.logger.debug("Page stabilized after action")
            return True
        except Exception as e:
            self.logger.debug(f"Page stability timeout (this is usually fine): {e}")
            return True
    
    async def run_task(self, task=None, start_url="https://www.google.com"):
        """Run a complete task from start to finish with better error tracking"""
        if not task:
            task = DEFAULT_TASK
        
        self.logger.log_session_start(task, start_url)
        
        # Initialize browser
        if not await self.initialize_browser():
            return False
        
        try:
            # Add initial delay to appear more human
            await self.human_like_delay()
            
            # Navigate to starting URL
            await self.page.goto(start_url, wait_until='networkidle')
            self.logger.info(f"Navigated to {start_url}")
            
            # Wait for page to fully load
            await self.wait_for_page_stability()
            
            # Add initial navigation to history
            self._add_to_history(0, {
                "action": "navigate",
                "target": start_url,
                "reasoning": "Initial navigation to starting URL"
            }, {"success": True, "message": f"Navigated to {start_url}"}, "")
            
            # Main execution loop
            success = await self.execute_task_loop(task)
            
            # Log final results
            actual_steps = len(self.history)
            self.logger.log_session_end(actual_steps, success)
            
            # Print final summary
            print(f"\nTask Execution Summary:")
            print(f"- Total steps taken: {actual_steps}")
            print(f"- Task completed successfully: {'Yes' if success else 'No'}")
            print(f"- Final URL: {self.page.url if self.page else 'Unknown'}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Task execution failed: {e}")
            print(f"Fatal error during task execution: {e}")
            return False
        finally:
            await self.cleanup()
    
    async def execute_task_loop(self, task):
        """Main execution loop for the task with robust error handling"""
        max_steps = SYSTEM_CONFIG["max_steps"]
        user_response = ""
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        for step in range(max_steps):
            self.logger.info(f"\n--- STEP {step + 1} of {max_steps} ---")
            
            try:
                # Get current page HTML
                raw_html = await self.page.content()
                
                # Check for CAPTCHA only if enabled in config
                if SYSTEM_CONFIG.get("check_captcha", False):
                    if await self.detect_captcha(raw_html):
                        self.logger.error("CAPTCHA detected - stopping execution")
                        await self.action_executor.take_screenshot(f"captcha_detected_step_{step + 1}.png")
                        return False
                
                # Get last action for context
                last_action = self.history[-1]['action'] if self.history else None
                
                # Process HTML WITH diff awareness
                processed_data = self.html_processor.process_with_diff(raw_html, self.html_differ, last_action)
                
                # Use the diff-aware HTML for LLM
                html_for_llm = processed_data["html_for_llm"]
                interactive_elements = processed_data["interactive_elements"]
                diff_info = processed_data.get("diff_info", {})
                change_context = processed_data.get("change_context", "")
                
                self.logger.log_html_processing(len(raw_html), len(html_for_llm))
                
                # Log diff information
                if diff_info.get('has_changes'):
                    self.logger.info(f"HTML Changes: {diff_info['change_summary']}")
                    self.logger.info(f"Change Context: {change_context}")
                else:
                    self.logger.info("No significant HTML changes detected")
                
                # Build context with history and user response
                context = f"Summary of the current page:\n"
                
                # Call LLM to summarize the HTML with change context
                summary_response = await self.llm_client.summarize_html(
                    html_for_llm, 
                    task,
                    change_context
                )
                
                if not summary_response["success"]:
                    self.logger.error(f"HTML summarization failed: {summary_response['error']}")
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        self.logger.error("Too many consecutive failures - stopping execution")
                        return False
                    continue
                
                html_summary = summary_response["summary"]
                context += html_summary + "\n\n"
                
                # Add interactive elements context
                context += f"Available interactive elements (for reference):\n{json.dumps(interactive_elements, indent=2)}\n\n"
                
                # Add diff context to help LLM understand what changed
                if diff_info.get('has_changes') and change_context:
                    context += f"Content changes since last action:\n{change_context}\n"
                    context += f"Change summary: {diff_info.get('change_summary', 'N/A')}\n\n"
                
                # Add consecutive failure context if applicable
                if consecutive_failures > 0:
                    context += f"Warning: {consecutive_failures} consecutive failures occurred. Consider alternative approaches.\n\n"
                
                history_context = self._build_history_context()
                
                # Append user response if it exists
                if user_response:
                    context += f"User's response from last 'ask' action: {user_response}\n\n"
                    user_response = ""
                
                # Get action from LLM with enhanced error handling
                max_llm_retries = 3
                llm_response = None
                
                for retry in range(max_llm_retries):
                    try:
                        llm_response = await self.llm_client.get_action(html_for_llm, task, context, history_context)
                        if llm_response["success"]:
                            break
                        else:
                            self.logger.warning(f"LLM attempt {retry + 1} failed: {llm_response['error']}")
                            if retry < max_llm_retries - 1:
                                await asyncio.sleep(1)  # Brief delay before retry
                    except Exception as e:
                        self.logger.error(f"LLM attempt {retry + 1} exception: {e}")
                        if retry < max_llm_retries - 1:
                            await asyncio.sleep(1)
                
                if not llm_response or not llm_response["success"]:
                    self.logger.error(f"All LLM attempts failed. Last error: {llm_response.get('error', 'Unknown') if llm_response else 'No response'}")
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        self.logger.error("Too many consecutive LLM failures - stopping execution")
                        return False
                    continue
                
                # Reset consecutive failures on success
                consecutive_failures = 0
                
                action_data = llm_response["action"]
                self.logger.info(f"LLM suggests action: {action_data}")
                
                # Validate action
                valid, validation_msg = self.action_executor.validate_action(action_data)
                if not valid:
                    self.logger.error(f"Invalid action: {validation_msg}")
                    continue
                
                # Check for completion action first
                if action_data.get("action") == "none":
                    self.logger.info("Task completed (LLM indicates completion)")
                    return True
                
                # Handle 'ask' and 'tell' actions before executing others
                if action_data.get("action") == "ask":
                    self.logger.info(f"AI asks: {action_data.get('text')}")
                    user_response = input("Your response: ")
                    result = {"success": True, "message": f"User responded: {user_response}"}
                    self._add_to_history(step + 1, action_data, result, "No HTML for this step")
                    continue
                
                if action_data.get("action") == "tell":
                    self.logger.info(f"AI tells: {action_data.get('text')}")
                    result = {"success": True, "message": f"Told user: {action_data.get('text')}"}
                    self._add_to_history(step + 1, action_data, result, "No HTML for this step")
                    continue
                
                # Add human-like delay before action
                await self.human_like_delay()
                
                # Execute action with retry logic
                max_action_retries = 2
                result = None
                
                for action_retry in range(max_action_retries):
                    try:
                        self.logger.info(f"Executing action (attempt {action_retry + 1}): {action_data.get('action')} on {action_data.get('target')}")
                        result = await self.action_executor.execute_action(action_data)
                        
                        if result.get("success"):
                            break
                        else:
                            self.logger.warning(f"Action attempt {action_retry + 1} failed: {result.get('error')}")
                            if action_retry < max_action_retries - 1:
                                await asyncio.sleep(2)  # Wait before retry
                                
                    except Exception as e:
                        self.logger.error(f"Action attempt {action_retry + 1} exception: {e}")
                        result = {"success": False, "error": str(e)}
                        if action_retry < max_action_retries - 1:
                            await asyncio.sleep(2)
                
                self.logger.info(f"Action result: {result}")
                
                # Wait for the action to complete and page to stabilize
                if result.get("success"):
                    self.logger.info("Waiting for page to stabilize after action...")
                    await self.wait_for_page_stability()
                
                # Add to history
                html_snippet = html_for_llm[:500] + "..." if len(html_for_llm) > 500 else html_for_llm
                self._add_to_history(step + 1, action_data, result, html_snippet)
                
                self.logger.log_step(step + 1, action_data, result)
                self.logger.log_history_summary(len(self.history))
                
                if not result["success"]:
                    # Try to recover from error with history context
                    await self.handle_error(action_data, result, task, html_for_llm)
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0  # Reset on successful action
                
                # Check if we should stop due to too many failures
                if consecutive_failures >= max_consecutive_failures:
                    self.logger.error(f"Too many consecutive failures ({consecutive_failures}) - stopping execution")
                    return False
                
                # Additional delay after action processing
                await asyncio.sleep(0.5)
                    
            except KeyboardInterrupt:
                self.logger.info("Execution interrupted by user")
                return False
            except Exception as e:
                self.logger.error(f"Step {step + 1} failed with exception: {e}")
                
                if SYSTEM_CONFIG["screenshot_on_error"]:
                    try:
                        screenshot_path = f"error_screenshot_step_{step + 1}.png"
                        await self.action_executor.take_screenshot(screenshot_path)
                        self.logger.info(f"Error screenshot saved: {screenshot_path}")
                    except:
                        pass
                
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    self.logger.error("Too many consecutive exceptions - stopping execution")
                    return False
                
                continue
        
        self.logger.warning(f"Reached maximum steps ({max_steps}) without completion")
        return False
    
    async def handle_error(self, failed_action, error_result, task, html):
        """Handle action execution errors"""
        self.logger.warning(f"Handling error for action: {failed_action}")
        
        error_msg = error_result.get("error", "Unknown error")
        history_context = self._build_history_context()
        
        recovery_response = await self.llm_client.handle_error(html, error_msg, task, history_context)
        
        if recovery_response["success"]:
            recovery_action = recovery_response["action"]
            self.logger.info(f"Attempting recovery action: {recovery_action}")
            
            # Add delay before recovery
            await self.human_like_delay()
            
            # Execute recovery action
            recovery_result = await self.action_executor.execute_action(recovery_action)
            
            # Wait for recovery action to complete
            if recovery_result.get("success"):
                await self.wait_for_page_stability()
            
            # Add recovery attempt to history
            html_snippet = html[:500] + "..." if len(html) > 500 else html
            self._add_to_history(len(self.history) + 1, recovery_action, recovery_result, html_snippet)
            
            self.logger.info(f"Recovery result: {recovery_result}")
        else:
            self.logger.error(f"Recovery failed: {recovery_response['error']}")
    
    def _add_to_history(self, step, action_data, result, html_snippet):
        """Add an action and its result to history"""
        history_entry = {
            'step': step,
            'timestamp': datetime.now().isoformat(),
            'action': action_data,
            'result': result,
            'html_snippet': html_snippet,
            'success': result.get('success', False)
        }
        self.history.append(history_entry)
    
    def _build_history_context(self):
        """Build a context string from history with smart summarization"""
        if not self.history:
            return "This is the first action. You are just starting the task."
        
        history_limit = SYSTEM_CONFIG.get("history_context_limit", None)
        recent_detail_limit = SYSTEM_CONFIG.get("history_summary_recent", 10)
        
        context_parts = [f"You have taken {len(self.history)} actions so far."]
        
        if history_limit is None:
            history_to_show = self.history
        else:
            history_to_show = self.history[-history_limit:] if len(self.history) > history_limit else self.history
        
        recent_history = history_to_show[-recent_detail_limit:] if len(history_to_show) > recent_detail_limit else history_to_show
        
        if len(history_to_show) > recent_detail_limit:
            older_history = history_to_show[:-recent_detail_limit]
            older_summary = {}
            older_success_count = 0
            
            for entry in older_history:
                action_type = entry['action'].get('action', 'unknown')
                older_summary[action_type] = older_summary.get(action_type, 0) + 1
                if entry['success']:
                    older_success_count += 1
            
            context_parts.append(f"Earlier actions summary (steps 1-{len(older_history)}): {dict(older_summary)} "
                            f"({older_success_count}/{len(older_history)} successful)")
        
        context_parts.append(f"Recent detailed history (last {len(recent_history)} actions):")
        
        for entry in recent_history:
            action = entry['action']
            result = entry['result']
            success_status = "✓" if entry['success'] else "✗"
            
            context_parts.append(
                f"Step {entry['step']}: {success_status} {action.get('action', 'unknown')} "
                f"on '{action.get('target', 'N/A')}' - {result.get('message', result.get('error', 'No message'))}"
            )
        
        total_actions = len(self.history)
        successful_actions = sum(1 for entry in self.history if entry['success'])
        success_rate = (successful_actions / total_actions * 100) if total_actions > 0 else 0
        
        context_parts.append(f"Overall progress: {successful_actions}/{total_actions} actions successful ({success_rate:.1f}%)")
        
        remaining_steps = SYSTEM_CONFIG["max_steps"] - len(self.history)
        if remaining_steps > 5:
            context_parts.append(f"Continue working towards the task goal. You have {remaining_steps} steps remaining.")
        elif remaining_steps > 0:
            context_parts.append(f"You're near the step limit ({remaining_steps} remaining). Focus on completing the task.")
        
        return "\n".join(context_parts)
    
    def get_history_summary(self):
        """Get a summary of the action history"""
        if not self.history:
            return "No actions taken yet."
        
        total_actions = len(self.history)
        successful_actions = sum(1 for entry in self.history if entry['success'])
        failed_actions = total_actions - successful_actions
        
        return {
            'total_actions': total_actions,
            'successful_actions': successful_actions,
            'failed_actions': failed_actions,
            'success_rate': successful_actions / total_actions if total_actions > 0 else 0,
            'last_action': self.history[-1] if self.history else None
        }
    
    async def cleanup(self):
        """Clean up resources"""
        try:
            if self.browser:
                await self.browser.close()
                self.logger.info("Browser closed successfully")
                
            summary = self.get_history_summary()
            self.logger.info(f"Final history summary: {summary}")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

async def main():
    """Main entry point"""
    print("Computer Use AI - Starting...")
    
    task = DEFAULT_TASK
    start_url = START_URL
    
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        print(f"Custom task: {task}")
    
    ai_system = ComputerUseAI()
    success = await ai_system.run_task(task, start_url)
    
    if success:
        print("Task completed successfully!")
        return 0
    else:
        print("Task failed or incomplete.")
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