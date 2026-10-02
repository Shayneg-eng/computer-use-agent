import os
import pyautogui
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import time
import re
from openai import OpenAI
import json

class DeepSeekVisualClickBot:
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = OpenAI(
            api_key=api_key, 
            base_url="https://api.deepseek.com"
        )
        
        # Configure pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5
        
        # Try to configure tesseract path (adjust if needed)
        # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Windows
        
    def capture_screen(self, region=None):
        """Capture screen or specific region"""
        if region:
            screenshot = pyautogui.screenshot(region=region)
        else:
            screenshot = pyautogui.screenshot()
        return screenshot
    
    def preprocess_image_for_ocr(self, image):
        """Enhance image quality for better OCR results"""
        # Convert to grayscale
        gray = image.convert('L')
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(2.0)
        
        # Apply slight blur to reduce noise
        blurred = enhanced.filter(ImageFilter.MedianFilter())
        
        # Scale up for better OCR
        width, height = blurred.size
        scaled = blurred.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
        
        return scaled
    
    def extract_text_with_positions(self, image):
        """Extract text and approximate positions using OCR"""
        try:
            # Preprocess image
            processed_image = self.preprocess_image_for_ocr(image)
            
            # Get text with bounding boxes
            ocr_data = pytesseract.image_to_data(processed_image, output_type=pytesseract.Output.DICT)
            
            text_elements = []
            width_scale = image.width / processed_image.width
            height_scale = image.height / processed_image.height
            
            for i in range(len(ocr_data['text'])):
                text = ocr_data['text'][i].strip()
                confidence = int(ocr_data['conf'][i])
                
                if text and confidence > 30:  # Filter low confidence text
                    # Scale coordinates back to original image size
                    x = int(ocr_data['left'][i] * width_scale)
                    y = int(ocr_data['top'][i] * height_scale)
                    w = int(ocr_data['width'][i] * width_scale)
                    h = int(ocr_data['height'][i] * height_scale)
                    
                    # Calculate center coordinates
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
    
    def analyze_text_for_click_target(self, text_elements, instruction):
        """Use DeepSeek to analyze OCR text and find click target"""
        
        # Prepare text data for the AI
        text_summary = "Detected text elements on screen:\n"
        for i, element in enumerate(text_elements):
            text_summary += f"{i+1}. Text: '{element['text']}' at position ({element['center'][0]}, {element['center'][1]})\n"
        
        if not text_elements:
            text_summary = "No text detected on screen."
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system", 
                        "content": """You are a UI automation assistant. Given a list of text elements detected on screen with their positions, help identify where to click for a given instruction.

Respond with ONLY a JSON object in this exact format:
{
    "target_text": "exact text to click on",
    "coordinates": [x, y],
    "confidence": 0.95,
    "reasoning": "brief explanation"
}

If no suitable target is found, set confidence to 0.0"""
                    },
                    {
                        "role": "user", 
                        "content": f"""Instruction: {instruction}

{text_summary}

Find the best text element to click for this instruction and return the coordinates."""
                    }
                ],
                stream=False,
                temperature=0.1
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Try to parse JSON response
            try:
                # Extract JSON from response if it's wrapped in other text
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    return {"confidence": 0.0, "reasoning": "Could not parse AI response"}
            except json.JSONDecodeError:
                return {"confidence": 0.0, "reasoning": "Invalid JSON in AI response"}
                
        except Exception as e:
            print(f"DeepSeek API Error: {e}")
            return {"confidence": 0.0, "reasoning": f"API Error: {str(e)}"}
    
    def find_clickable_elements(self, image):
        """Detect common clickable UI patterns"""
        clickable_patterns = []
        
        # Convert to text elements
        text_elements = self.extract_text_with_positions(image)
        
        # Look for common clickable text patterns
        clickable_keywords = [
            'button', 'click', 'submit', 'send', 'login', 'sign in', 'sign up',
            'register', 'search', 'go', 'next', 'previous', 'close', 'cancel',
            'ok', 'yes', 'no', 'apply', 'save', 'delete', 'edit', 'add',
            'menu', 'home', 'back', 'forward', 'download', 'upload'
        ]
        
        for element in text_elements:
            text_lower = element['text'].lower()
            for keyword in clickable_keywords:
                if keyword in text_lower:
                    clickable_patterns.append({
                        'type': 'text_button',
                        'text': element['text'],
                        'center': element['center'],
                        'confidence': element['confidence']
                    })
                    break
        
        return clickable_patterns
    
    def smart_click(self, instruction, max_attempts=3):
        """Main method to perform intelligent clicking"""
        
        for attempt in range(max_attempts):
            try:
                print(f"\nAttempt {attempt + 1}: {instruction}")
                
                # Capture screen
                screenshot = self.capture_screen()
                print("Screenshot captured")
                
                # Extract text with OCR
                text_elements = self.extract_text_with_positions(screenshot)
                print(f"Found {len(text_elements)} text elements")
                
                if not text_elements:
                    print("No text detected, trying to find common UI patterns...")
                    # Fallback: look for common clickable areas
                    clickable_elements = self.find_clickable_elements(screenshot)
                    if clickable_elements:
                        element = clickable_elements[0]
                        x, y = element['center']
                        pyautogui.click(x, y)
                        print(f"Clicked on detected UI element at ({x}, {y})")
                        return {'success': True, 'coordinates': (x, y)}
                    else:
                        print("No clickable elements found")
                        continue
                
                # Analyze with DeepSeek
                result = self.analyze_text_for_click_target(text_elements, instruction)
                
                print(f"AI Analysis: {result.get('reasoning', 'No reasoning provided')}")
                print(f"Confidence: {result.get('confidence', 0):.2f}")
                
                if result.get('confidence', 0) < 0.5:
                    print("Low confidence, retrying...")
                    time.sleep(1)
                    continue
                
                # Get coordinates
                coordinates = result.get('coordinates', [])
                if len(coordinates) != 2:
                    print("Invalid coordinates received")
                    continue
                
                x, y = coordinates
                
                # Validate coordinates
                screen_width, screen_height = pyautogui.size()
                if not (0 <= x <= screen_width and 0 <= y <= screen_height):
                    print(f"Coordinates ({x}, {y}) outside screen bounds")
                    continue
                
                # Perform click
                pyautogui.click(x, y)
                print(f"✅ Successfully clicked at ({x}, {y}) on '{result.get('target_text', 'unknown')}'")
                
                return {
                    'success': True, 
                    'coordinates': (x, y), 
                    'target_text': result.get('target_text', ''),
                    'reasoning': result.get('reasoning', '')
                }
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_attempts - 1:
                    return {'success': False, 'error': str(e)}
                time.sleep(2)
        
        return {'success': False, 'error': 'Max attempts reached'}
    
    def debug_ocr(self, save_image=True):
        """Debug method to test OCR capabilities"""
        screenshot = self.capture_screen()
        
        if save_image:
            screenshot.save("debug_screenshot.png")
            print("Screenshot saved as debug_screenshot.png")
        
        text_elements = self.extract_text_with_positions(screenshot)
        
        print(f"\n=== OCR DEBUG RESULTS ===")
        print(f"Found {len(text_elements)} text elements:")
        
        for i, element in enumerate(text_elements, 1):
            print(f"{i}. '{element['text']}' at {element['center']} (confidence: {element['confidence']})")
        
        return text_elements

# Usage example
def main():
    LLM_API_KEY = os.environ["DEEPSEEK_API_KEY"]
    
    # Initialize bot
    bot = DeepSeekVisualClickBot(LLM_API_KEY)
    
    # Debug OCR first
    print("Testing OCR capabilities...")
    bot.debug_ocr()
    
    # Example clicking tasks
    tasks = [
        "Click on the login button",
        "Click on the search box", 
        "Click on the submit button",
        "Click on the close button",
        "Click on the menu button"
    ]
    
    for task in tasks:
        print(f"\n{'='*60}")
        result = bot.smart_click(task)
        
        if result['success']:
            print(f"✅ Task completed: {task}")
            print(f"   Target: {result.get('target_text', 'N/A')}")
            print(f"   Position: {result['coordinates']}")
        else:
            print(f"❌ Task failed: {task}")
            print(f"   Error: {result.get('error', 'Unknown error')}")
        
        # Wait between tasks
        time.sleep(3)

if __name__ == "__main__":
    main()