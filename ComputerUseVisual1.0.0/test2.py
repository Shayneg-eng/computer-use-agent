import os
import pyautogui
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import time
import re
from openai import OpenAI
import json

class GoalOrientedVisualBot:
    def __init__(self, api_key, goal):
        self.api_key = api_key
        self.goal = goal
        self.client = OpenAI(
            api_key=api_key, 
            base_url="https://api.deepseek.com"
        )
        
        # Track progress and actions
        self.action_history = []
        self.step_count = 0
        self.max_steps = 20  # Prevent infinite loops
        
        # Configure pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 1.0  # Slower for more deliberate actions
        
    def capture_screen(self, region=None):
        """Capture screen or specific region"""
        if region:
            screenshot = pyautogui.screenshot(region=region)
        else:
            screenshot = pyautogui.screenshot()
        return screenshot
    
    def preprocess_image_for_ocr(self, image):
        """Enhance image quality for better OCR results"""
        gray = image.convert('L')
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)
        blurred = enhanced.filter(ImageFilter.MedianFilter())
        width, height = blurred.size
        scaled = blurred.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
        return scaled
    
    def extract_text_with_positions(self, image):
        """Extract text and approximate positions using OCR"""
        try:
            processed_image = self.preprocess_image_for_ocr(image)
            ocr_data = pytesseract.image_to_data(processed_image, output_type=pytesseract.Output.DICT)
            
            text_elements = []
            width_scale = image.width / processed_image.width
            height_scale = image.height / processed_image.height
            
            for i in range(len(ocr_data['text'])):
                text = ocr_data['text'][i].strip()
                confidence = int(ocr_data['conf'][i])
                
                if text and confidence > 30:
                    x = int(ocr_data['left'][i] * width_scale)
                    y = int(ocr_data['top'][i] * height_scale)
                    w = int(ocr_data['width'][i] * width_scale)
                    h = int(ocr_data['height'][i] * height_scale)
                    
                    center_x = x + w // 2
                    center_y = y + h // 2
                    
                    text_elements.append({
                        'text': text,
                        'confidence': confidence,
                        'bbox': (x, y, w, h),
                        'center': (center_x, center_y)
                    })
            
            return text_elements
            
        except Exception as e:
            print(f"OCR Error: {e}")
            return []
    
    def analyze_current_state_and_decide_action(self, text_elements):
        """AI analyzes current state and decides next action based on goal"""
        
        # Prepare context for the AI
        text_summary = "Current screen content:\n"
        for i, element in enumerate(text_elements):
            text_summary += f"{i+1}. '{element['text']}' at position ({element['center'][0]}, {element['center'][1]})\n"
        
        if not text_elements:
            text_summary = "No text detected on current screen."
        
        # Prepare action history
        history_summary = "Previous actions taken:\n"
        if self.action_history:
            for i, action in enumerate(self.action_history[-5:], 1):  # Last 5 actions
                history_summary += f"{i}. {action['action']} - {action['result']}\n"
        else:
            history_summary = "No previous actions taken."
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system", 
                        "content": f"""You are an AI automation assistant working towards a specific goal. 

GOAL: {self.goal}

Your job is to analyze the current screen and decide the next action to take towards achieving this goal.

You can perform these actions:
1. CLICK - Click on a specific text element
2. TYPE - Type text (you'll be asked what to type)
3. SCROLL - Scroll the page (up/down)
4. WAIT - Wait for page to load
5. COMPLETE - Goal has been achieved
6. FAILED - Goal cannot be achieved with current screen

Respond with ONLY a JSON object in this exact format:
{{
    "action": "CLICK|TYPE|SCROLL|WAIT|COMPLETE|FAILED",
    "target": "exact text to click on (for CLICK action)",
    "coordinates": [x, y],
    "reasoning": "why this action helps achieve the goal",
    "confidence": 0.95,
    "next_step": "what you expect to happen after this action"
}}

For TYPE action, set target to "INPUT_NEEDED" and specify what should be typed in reasoning.
For SCROLL action, set target to "UP" or "DOWN".
For WAIT/COMPLETE/FAILED actions, coordinates can be [0, 0]."""
                    },
                    {
                        "role": "user", 
                        "content": f"""GOAL: {self.goal}

Step {self.step_count + 1} of {self.max_steps}

{text_summary}

{history_summary}

What should be the next action to achieve the goal?"""
                    }
                ],
                stream=False,
                temperature=0.2
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    return {"action": "FAILED", "reasoning": "Could not parse AI response"}
            except json.JSONDecodeError:
                return {"action": "FAILED", "reasoning": "Invalid JSON in AI response"}
                
        except Exception as e:
            print(f"DeepSeek API Error: {e}")
            return {"action": "FAILED", "reasoning": f"API Error: {str(e)}"}
    
    def execute_action(self, action_plan, text_elements):
        """Execute the planned action"""
        action_type = action_plan.get('action', '').upper()
        
        try:
            if action_type == "CLICK":
                return self.execute_click(action_plan, text_elements)
            elif action_type == "TYPE":
                return self.execute_type(action_plan)
            elif action_type == "SCROLL":
                return self.execute_scroll(action_plan)
            elif action_type == "WAIT":
                return self.execute_wait(action_plan)
            elif action_type == "COMPLETE":
                return {"success": True, "message": "Goal achieved!", "complete": True}
            elif action_type == "FAILED":
                return {"success": False, "message": "Goal cannot be achieved", "complete": True}
            else:
                return {"success": False, "message": f"Unknown action: {action_type}"}
                
        except Exception as e:
            return {"success": False, "message": f"Action execution error: {str(e)}"}
    
    def execute_click(self, action_plan, text_elements):
        """Execute click action"""
        target_text = action_plan.get('target', '')
        coordinates = action_plan.get('coordinates', [])
        
        if len(coordinates) == 2:
            x, y = coordinates
            screen_width, screen_height = pyautogui.size()
            
            if 0 <= x <= screen_width and 0 <= y <= screen_height:
                pyautogui.click(x, y)
                return {"success": True, "message": f"Clicked on '{target_text}' at ({x}, {y})"}
            else:
                return {"success": False, "message": "Coordinates outside screen bounds"}
        else:
            return {"success": False, "message": "Invalid coordinates provided"}
    
    def execute_type(self, action_plan):
        """Execute typing action"""
        reasoning = action_plan.get('reasoning', '')
        
        # Extract what to type from reasoning or ask user
        print(f"AI wants to type something: {reasoning}")
        text_to_type = input("What should be typed? ")
        
        if text_to_type.strip():
            pyautogui.typewrite(text_to_type)
            return {"success": True, "message": f"Typed: '{text_to_type}'"}
        else:
            return {"success": False, "message": "No text provided to type"}
    
    def execute_scroll(self, action_plan):
        """Execute scroll action"""
        direction = action_plan.get('target', 'DOWN').upper()
        
        if direction == "UP":
            pyautogui.scroll(3)
            return {"success": True, "message": "Scrolled up"}
        elif direction == "DOWN":
            pyautogui.scroll(-3)
            return {"success": True, "message": "Scrolled down"}
        else:
            return {"success": False, "message": "Invalid scroll direction"}
    
    def execute_wait(self, action_plan):
        """Execute wait action"""
        wait_time = 2
        time.sleep(wait_time)
        return {"success": True, "message": f"Waited {wait_time} seconds"}
    
    def run_automation(self):
        """Main automation loop"""
        print(f"🎯 Starting automation with goal: {self.goal}")
        print(f"📝 Maximum steps allowed: {self.max_steps}")
        print("-" * 60)
        
        while self.step_count < self.max_steps:
            self.step_count += 1
            
            print(f"\n📍 Step {self.step_count}: Analyzing current state...")
            
            # Capture and analyze current screen
            screenshot = self.capture_screen()
            text_elements = self.extract_text_with_positions(screenshot)
            
            print(f"   Found {len(text_elements)} text elements on screen")
            
            # Let AI decide next action
            action_plan = self.analyze_current_state_and_decide_action(text_elements)
            
            print(f"🤖 AI Decision:")
            print(f"   Action: {action_plan.get('action', 'Unknown')}")
            print(f"   Target: {action_plan.get('target', 'N/A')}")
            print(f"   Reasoning: {action_plan.get('reasoning', 'No reasoning provided')}")
            print(f"   Confidence: {action_plan.get('confidence', 0):.2f}")
            print(f"   Expected: {action_plan.get('next_step', 'N/A')}")
            
            # Execute the action
            result = self.execute_action(action_plan, text_elements)
            
            # Record action in history
            self.action_history.append({
                "step": self.step_count,
                "action": action_plan.get('action', 'Unknown'),
                "target": action_plan.get('target', ''),
                "result": result.get('message', 'No result'),
                "success": result.get('success', False)
            })
            
            print(f"✅ Result: {result.get('message', 'No message')}")
            
            # Check if goal is complete or failed
            if result.get('complete', False):
                if result.get('success', False):
                    print(f"\n🎉 SUCCESS! Goal achieved in {self.step_count} steps!")
                else:
                    print(f"\n❌ FAILED! Could not achieve goal after {self.step_count} steps.")
                break
            
            if not result.get('success', False):
                print(f"⚠️  Action failed, but continuing...")
            
            # Wait between actions
            time.sleep(2)
        
        if self.step_count >= self.max_steps:
            print(f"\n⏰ Automation stopped: Maximum steps ({self.max_steps}) reached")
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print automation summary"""
        print(f"\n{'='*60}")
        print("AUTOMATION SUMMARY")
        print(f"{'='*60}")
        print(f"Goal: {self.goal}")
        print(f"Total steps: {self.step_count}")
        print(f"Actions taken:")
        
        for action in self.action_history:
            status = "✅" if action['success'] else "❌"
            print(f"  {action['step']}. {status} {action['action']} - {action['result']}")

# Usage example
def main():
    LLM_API_KEY = os.environ["DEEPSEEK_API_KEY"]
    
    # Example goals - uncomment one to test
    goals = [
        "Log into my Google account",
        "Search for 'Python automation' on Google",
        "Navigate to YouTube and search for 'AI tutorials'",
        "Find and click on the settings menu",
        "Create a new document or file",
        "Send an email",
        "Download a file from the current page"
    ]
    
    print("Available goals:")
    for i, goal in enumerate(goals, 1):
        print(f"{i}. {goal}")
    
    try:
        choice = int(input("\nSelect a goal (1-7) or enter 0 for custom goal: "))
        
        if choice == 0:
            goal = input("Enter your custom goal: ")
        elif 1 <= choice <= len(goals):
            goal = goals[choice - 1]
        else:
            print("Invalid choice, using default goal")
            goal = goals[0]
            
    except ValueError:
        goal = input("Enter your goal: ")
    
    print(f"\n🚀 Selected goal: {goal}")
    
    # Initialize and run the bot
    bot = GoalOrientedVisualBot(LLM_API_KEY, goal)
    
    input("\nPress Enter when you're ready to start automation...")
    
    try:
        bot.run_automation()
    except KeyboardInterrupt:
        print("\n\n⛔ Automation stopped by user")
        bot.print_summary()
    except Exception as e:
        print(f"\n\n💥 Automation crashed: {e}")
        bot.print_summary()

if __name__ == "__main__":
    main()