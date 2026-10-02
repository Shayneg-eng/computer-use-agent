import os
import openai
import tkinter as tk
from tkinter import messagebox
import base64
import io
from PIL import Image, ImageGrab
import threading
import time

class AIScreenAnalyzer:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=os.getenv("POE_API_KEY", ""),
            base_url="https://api.poe.com/v1",
        )
        
        self.root = tk.Tk()
        self.root.title("AI Screen Analyzer")
        self.root.geometry("800x700")
        
        self.running = False
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = tk.Frame(self.root)
        main_frame.pack(expand=True, fill='both', padx=20, pady=20)
        
        # Title
        title_label = tk.Label(main_frame, text="AI Screen Analyzer", 
                              font=("Arial", 18, "bold"))
        title_label.pack(pady=(0, 15))
        
        # Controls frame (upper part)
        controls_frame = tk.Frame(main_frame)
        controls_frame.pack(fill='x', pady=(0, 20))
        
        # Buttons frame
        button_frame = tk.Frame(controls_frame)
        button_frame.pack(pady=(0, 15))
        
        # Start/Stop analysis button
        self.analysis_btn = tk.Button(button_frame, text="Start Screen Analysis", 
                                     command=self.toggle_analysis, 
                                     bg="#4CAF50", fg="white", font=("Arial", 12),
                                     width=20, height=2)
        self.analysis_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Single screenshot button
        screenshot_btn = tk.Button(button_frame, text="Analyze Current Screen", 
                                  command=self.analyze_single_screenshot,
                                  bg="#2196F3", fg="white", font=("Arial", 12),
                                  width=20, height=2)
        screenshot_btn.pack(side=tk.LEFT)
        
        # Settings frame
        settings_frame = tk.Frame(controls_frame)
        settings_frame.pack(fill='x', pady=(0, 15))
        
        # Interval setting
        interval_frame = tk.Frame(settings_frame)
        interval_frame.pack(pady=(0, 10))
        
        tk.Label(interval_frame, text="Analysis Interval:", font=("Arial", 12)).pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value="5")
        interval_entry = tk.Entry(interval_frame, textvariable=self.interval_var, width=5, font=("Arial", 12))
        interval_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(interval_frame, text="seconds", font=("Arial", 12)).pack(side=tk.LEFT)
        
        # Custom prompt frame
        prompt_frame = tk.Frame(settings_frame)
        prompt_frame.pack(fill='x')
        
        tk.Label(prompt_frame, text="Analysis Prompt:", font=("Arial", 12, "bold")).pack(anchor='w')
        
        # Create a frame for the text widget and scrollbar
        text_frame = tk.Frame(prompt_frame)
        text_frame.pack(fill='x', pady=(5, 0))
        
        # Auto-resizing text widget for prompt
        self.prompt_text = tk.Text(text_frame, font=("Arial", 11), wrap=tk.WORD, 
                                  height=2, relief="solid", borderwidth=1,
                                  padx=8, pady=5)
        
        # Scrollbar for the prompt text (only appears when needed)
        prompt_scrollbar = tk.Scrollbar(text_frame, orient="vertical", command=self.prompt_text.yview)
        self.prompt_text.configure(yscrollcommand=prompt_scrollbar.set)
        
        self.prompt_text.pack(side=tk.LEFT, expand=True, fill='both')
        prompt_scrollbar.pack(side=tk.RIGHT, fill='y')
        
        # Set default prompt
        default_prompt = "Analyze this screenshot and describe what you see on the screen."
        self.prompt_text.insert("1.0", default_prompt)
        
        # Bind events for auto-resizing
        self.prompt_text.bind('<KeyPress>', self.on_prompt_change)
        self.prompt_text.bind('<KeyRelease>', self.on_prompt_change)
        self.prompt_text.bind('<Button-1>', self.on_prompt_change)
        self.prompt_text.bind('<FocusIn>', self.on_prompt_change)
        
        # Initial resize
        self.root.after(100, self.resize_prompt_text)
        
        # Status label
        self.status_label = tk.Label(controls_frame, text="Ready", fg="green", font=("Arial", 12, "bold"))
        self.status_label.pack(pady=(10, 0))
        
        # Output frame (lower part)
        output_frame = tk.Frame(main_frame)
        output_frame.pack(expand=True, fill='both')
        
        # Output label and controls
        output_header = tk.Frame(output_frame)
        output_header.pack(fill='x', pady=(0, 10))
        
        tk.Label(output_header, text="AI Analysis Results:", font=("Arial", 14, "bold"), fg="#2c3e50").pack(side=tk.LEFT)
        
        # Output control buttons
        output_controls = tk.Frame(output_header)
        output_controls.pack(side=tk.RIGHT)
        
        clear_btn = tk.Button(output_controls, text="Clear All", command=self.clear_output,
                             bg="#e74c3c", fg="white", font=("Arial", 9),
                             relief="flat", padx=15)
        clear_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        copy_btn = tk.Button(output_controls, text="Copy Latest", command=self.copy_latest_response,
                            bg="#3498db", fg="white", font=("Arial", 9),
                            relief="flat", padx=15)
        copy_btn.pack(side=tk.LEFT)
        
        # Output text widget with scrollbar
        output_text_frame = tk.Frame(output_frame)
        output_text_frame.pack(expand=True, fill='both')
        
        self.output_text = tk.Text(output_text_frame, wrap=tk.WORD, font=("Segoe UI", 11),
                                  bg="#f8f9fa", fg="#2c3e50", relief="solid", borderwidth=1,
                                  padx=15, pady=15, selectbackground="#3498db")
        
        # Scrollbar for output
        output_scrollbar = tk.Scrollbar(output_text_frame, orient="vertical", command=self.output_text.yview)
        self.output_text.configure(yscrollcommand=output_scrollbar.set)
        
        self.output_text.pack(side=tk.LEFT, expand=True, fill='both')
        output_scrollbar.pack(side=tk.RIGHT, fill='y')
        
        # Store latest response for copying
        self.latest_response = ""
        
        # Add initial message
        welcome_msg = "Welcome to AI Screen Analyzer!\n\nClick 'Analyze Current Screen' for a one-time analysis or 'Start Screen Analysis' for continuous monitoring.\n\nAI responses will appear here...\n\n"
        self.output_text.insert(tk.END, welcome_msg)
        self.output_text.config(state=tk.DISABLED)
        
    def on_prompt_change(self, event=None):
        """Called when prompt text changes to trigger resize"""
        self.root.after_idle(self.resize_prompt_text)
    
    def resize_prompt_text(self):
        """Automatically resize the prompt text widget based on content"""
        try:
            # Get the current content
            content = self.prompt_text.get("1.0", "end-1c")
            
            # Count lines in the content
            lines = content.split('\n')
            num_lines = len(lines)
            
            # Calculate the height needed based on line wrapping
            text_width = self.prompt_text.winfo_width()
            if text_width > 1:  # Make sure widget is initialized
                font = self.prompt_text.cget("font")
                # Estimate character width (this is approximate)
                char_width = 8  # Average character width in pixels for Arial 11
                chars_per_line = max(1, (text_width - 20) // char_width)  # Account for padding
                
                wrapped_lines = 0
                for line in lines:
                    if len(line) == 0:
                        wrapped_lines += 1
                    else:
                        wrapped_lines += max(1, (len(line) + chars_per_line - 1) // chars_per_line)
                
                # Set minimum and maximum height
                min_height = 2
                max_height = 6
                new_height = max(min_height, min(max_height, wrapped_lines))
                
                # Only update if height changed
                current_height = int(self.prompt_text.cget("height"))
                if new_height != current_height:
                    self.prompt_text.config(height=new_height)
        except:
            # If there's any error, just use default height
            pass
    
    def get_prompt_text(self):
        """Get the current prompt text"""
        return self.prompt_text.get("1.0", "end-1c")
    
    def capture_screenshot(self):
        """Capture a screenshot of the entire screen"""
        try:
            screenshot = ImageGrab.grab()
            return screenshot
        except Exception as e:
            print(f"Error capturing screenshot: {e}")
            return None
    
    def encode_image_to_base64(self, image):
        """Convert PIL Image to base64 string"""
        buffer = io.BytesIO()
        # Resize image to reduce API costs
        image.thumbnail((1024, 768), Image.Resampling.LANCZOS)
        image.save(buffer, format='JPEG', quality=85)
        image_data = buffer.getvalue()
        return base64.b64encode(image_data).decode('utf-8')
    
    def analyze_screenshot(self, image, custom_prompt=None):
        """Send screenshot to AI and get response"""
        try:
            self.update_status("Analyzing screenshot...", "orange")
            
            # Convert image to base64
            base64_image = self.encode_image_to_base64(image)
            
            # Use custom prompt or get from text widget
            prompt = custom_prompt or self.get_prompt_text()
            
            # Create chat completion with image
            chat = self.client.chat.completions.create(
                model="GPT-OSS-120B-CS",
                messages=[
                    {
                        "role": "user", 
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
            )
            
            self.update_status("Analysis complete", "green")
            return chat.choices[0].message.content
            
        except Exception as e:
            error_msg = f"Error analyzing screenshot: {str(e)}"
            self.update_status("Analysis failed", "red")
            return error_msg
    
    def add_response_to_output(self, response):
        """Add AI response to the main output text widget"""
        timestamp = time.strftime("%H:%M:%S")
        
        # Enable text widget for editing
        self.output_text.config(state=tk.NORMAL)
        
        # Check if this is the first real response (remove welcome message)
        current_content = self.output_text.get("1.0", tk.END)
        if "Welcome to AI Screen Analyzer!" in current_content and "AI responses will appear here..." in current_content:
            self.output_text.delete("1.0", tk.END)
        
        # Add separator if there's already content
        existing_content = self.output_text.get("1.0", tk.END).strip()
        separator = "\n" + "="*80 + "\n" if existing_content else ""
        
        # Format and add new response
        new_content = f"{separator}[{timestamp}] Analysis:\n\n{response}\n\n"
        
        self.output_text.insert(tk.END, new_content)
        self.output_text.see(tk.END)
        
        # Store latest response
        self.latest_response = response
        
        # Disable text widget to prevent user editing
        self.output_text.config(state=tk.DISABLED)
    
    def clear_output(self):
        """Clear all text from output"""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        
        # Add back welcome message
        welcome_msg = "Output cleared. New AI responses will appear here...\n\n"
        self.output_text.insert(tk.END, welcome_msg)
        self.output_text.config(state=tk.DISABLED)
        
        self.latest_response = ""
    
    def copy_latest_response(self):
        """Copy the latest response to clipboard"""
        if self.latest_response:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.latest_response)
            
            # Brief visual feedback
            original_text = self.status_label.cget("text")
            original_color = self.status_label.cget("fg")
            self.status_label.config(text="Copied to clipboard!", fg="blue")
            self.root.after(2000, lambda: self.status_label.config(text=original_text, fg=original_color))
        else:
            messagebox.showinfo("No Content", "No response to copy yet.")
    
    def update_status(self, message, color="black"):
        """Update status label"""
        self.status_label.config(text=message, fg=color)
        self.root.update_idletasks()
    
    def analysis_loop(self):
        """Main screenshot capture and analysis loop"""
        try:
            interval = float(self.interval_var.get())
        except ValueError:
            interval = 5.0
            
        while self.running:
            # Capture screenshot
            screenshot = self.capture_screenshot()
            if screenshot:
                # Analyze screenshot
                response = self.analyze_screenshot(screenshot)
                
                # Add response to output
                self.root.after(0, lambda r=response: self.add_response_to_output(r))
                
            # Wait for the specified interval
            time.sleep(interval)
    
    def toggle_analysis(self):
        """Start or stop continuous screen analysis"""
        if not self.running:
            # Start analysis
            self.running = True
            self.analysis_btn.config(text="Stop Screen Analysis", bg="#e74c3c")
            self.update_status("Running continuous analysis...", "blue")
            
            # Start analysis thread
            self.analysis_thread = threading.Thread(target=self.analysis_loop, daemon=True)
            self.analysis_thread.start()
            
        else:
            # Stop analysis
            self.running = False
            self.analysis_btn.config(text="Start Screen Analysis", bg="#4CAF50")
            self.update_status("Analysis stopped", "gray")
    
    def analyze_single_screenshot(self):
        """Capture and analyze a single screenshot"""
        self.update_status("Capturing screenshot...", "blue")
        
        def single_analysis():
            screenshot = self.capture_screenshot()
            if screenshot:
                # Analyze screenshot
                response = self.analyze_screenshot(screenshot)
                
                # Add response to output
                self.root.after(0, lambda: self.add_response_to_output(response))
        
        # Run in separate thread to avoid blocking UI
        thread = threading.Thread(target=single_analysis, daemon=True)
        thread.start()
    
    def run(self):
        """Start the application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Clean up when closing the application"""
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    # Check if required packages are installed
    try:
        from PIL import Image, ImageGrab
    except ImportError:
        print("Please install required packages:")
        print("pip install pillow openai")
        exit(1)
    
    app = AIScreenAnalyzer()
    app.run()