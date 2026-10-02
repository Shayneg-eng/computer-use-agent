import os
import pyautogui
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import time
import re
from openai import OpenAI
import json

class WorkModeBot:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = OpenAI(
            api_key=api_key, 
            base_url="https://api.deepseek.com"
        )
        
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5
        
        # Work mode patterns - common buttons to look for
        self.work_patterns = [
            'next', 'continue', 'submit', 'answer', 'correct', 'right',
            'true', 'false', 'yes', 'no', 'done', 'finish', 'complete',
            'check', 'verify', 'confirm', 'proceed', 'forward', 'go'
        ]
    
    def capture_screen(self):
        return pyautogui.screenshot()
    
    def preprocess_image_for_ocr(self, image):
        gray = image.convert('L')
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)
        blurred = enhanced.filter(ImageFilter.MedianFilter())
        width, height = blurred.size
        scaled = blurred.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
        return scaled
    
    def extract_text_with_positions(self, image):
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
                        'center': (center_x, center_y)
                    })
            
            return text_elements
        except:
            return []
    
    def find_work_button(self, text_elements):
        """Find best work-related button to click"""
        
        text_summary = ""
        for element in text_elements:
            text_summary += f"'{element['text']}' at {element['center']}\n"
        
        if not text_elements:
            return {"action": "WAIT", "target": "", "coordinates": [0, 0]}
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system", 
                        "content": """You are a work automation bot. Find the best button to click for schoolwork/tests.

Priority order:
1. Answer buttons (A, B, C, D, True, False, Yes, No)
2. Next/Continue buttons
3. Submit/Check buttons

Respond with ONLY this JSON:
{
    "action": "CLICK",
    "target": "exact text",
    "coordinates": [x, y],
    "reason": "max 10 words"
}"""
                    },
                    {
                        "role": "user", 
                        "content": f"Find best button to click:\n{text_summary}"
                    }
                ],
                stream=False,
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                return json.loads(json_match.group())
            else:
                return {"action": "WAIT", "target": "", "coordinates": [0, 0], "reason": "No response"}
                
        except:
            return {"action": "WAIT", "target": "", "coordinates": [0, 0], "reason": "API error"}
    
    def execute_click(self, coordinates):
        """Execute click at coordinates"""
        if len(coordinates) == 2:
            x, y = coordinates
            screen_width, screen_height = pyautogui.size()
            
            if 0 <= x <= screen_width and 0 <= y <= screen_height:
                pyautogui.click(x, y)
                return True
        return False
    
    def work_step(self):
        """Single work step - analyze and click"""
        # Capture screen
        screenshot = self.capture_screen()
        text_elements = self.extract_text_with_positions(screenshot)
        
        # Find button to click
        decision = self.find_work_button(text_elements)
        
        action = decision.get('action', 'WAIT')
        target = decision.get('target', '')
        coordinates = decision.get('coordinates', [0, 0])
        reason = decision.get('reason', 'No reason')
        
        # Simple output
        print(f"{reason} → {action} {target}")
        
        if action == "CLICK" and coordinates != [0, 0]:
            success = self.execute_click(coordinates)
            if success:
                time.sleep(2)  # Wait after click
                return True
        
        time.sleep(1)  # Wait if no action
        return False
    
    def continuous_work(self):
        """Continuous work mode"""
        print("🔄 Work mode started - Press Ctrl+C to stop")
        step = 0
        
        try:
            while True:
                step += 1
                print(f"Step {step}: ", end="")
                self.work_step()
                
        except KeyboardInterrupt:
            print(f"\n⛔ Stopped after {step} steps")

# Quick start functions
def work_mode():
    """Start work mode immediately"""
    LLM_API_KEY = os.environ["DEEPSEEK_API_KEY"]
    bot = WorkModeBot(LLM_API_KEY)
    bot.continuous_work()

def single_step():
    """Do one work step"""
    LLM_API_KEY = os.environ["DEEPSEEK_API_KEY"]
    bot = WorkModeBot(LLM_API_KEY)
    bot.work_step()

# Main interface
def main():
    print("Work Bot Commands:")
    print("1. work_mode() - Continuous automation")
    print("2. single_step() - One step only")
    
    choice = input("\nEnter 1 or 2: ")
    
    if choice == "1":
        work_mode()
    elif choice == "2":
        single_step()
    else:
        print("Invalid choice")

if __name__ == "__main__":
    # Quick start - uncomment one:
    work_mode()        # For continuous work
    # single_step()      # For single step
    main()               # For menu