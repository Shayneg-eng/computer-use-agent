import os
# Configuration file for Computer Use AI

# LLM Configuration
LLM_CONFIG = {
    "api_key": os.getenv("POE_API_KEY", ""),
    "base_url": "https://api.poe.com/v1",
    "model": "Qwen3-235B-Think-CS",
    "max_tokens": 10000,
    "temperature": 0.1
}

# Browser Configuration
BROWSER_CONFIG = {
    "headless": False,
    "viewport": {"width": 1280, "height": 720},
    "timeout": 30000,
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "extra_http_headers": {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    },
    "locale": "en-US",
    "timezone_id": "America/New_York"
}

# System Configuration
SYSTEM_CONFIG = {
    "max_steps": 100,               # Allow many steps for complex tasks
    "html_truncate_length": 8000,
    "screenshot_on_error": True,
    "log_level": "INFO",
    "history_context_limit": None,  # Show ALL history
    "history_summary_recent": 25,   # Show last 25 in detail
    "human_like_delays": True,
    "min_delay": 3,
    "max_delay": 6,
    "check_captcha": False
}

# LLM Prompts
PROMPTS = {
    "system_prompt": """You control a web browser to complete tasks. Analyze the HTML and action history to decide your next action. Continue until the task is fully complete.
    
CRITICAL: Respond with ONLY valid JSON. No markdown, explanations, or other text. If you need to communicate with the user, use the 'ask' or 'tell' actions.""",
    
    "main_prompt": """HTML: {html}
Task: {task}

Choose your next action to progress toward task completion. Only use "none" when completely finished.

JSON format only:
{{
  "action": "click|navigate|type|scroll|wait|none|ask|tell",
  "target": "CSS selector or URL",
  "text": "text input or question/message to user",
  "reasoning": "why this action progresses the task"
}}

Actions:
- click: Click element (CSS selector)
- navigate: Go to URL
- type: Enter text (CSS selector + text)
- scroll: "up|down|top|bottom"
- wait: Seconds to wait
- ask: Pose a question to the user (text field)
- tell: Provide a statement to the user (text field)
- none: Task complete only""",

    "error_prompt": """Error occurred. HTML: {html}
Error: {error}

Previous action failed. Try a different approach. Don't give up.

JSON only:
{{
  "action": "click|navigate|type|scroll|wait|none|ask|tell",
  "target": "CSS selector or URL",
  "text": "text input or question/message to user", 
  "reasoning": "alternative approach explanation"
}}"""
}

# Default starting task
DEFAULT_TASK = "find an italian restaurant go to their website and make a reservation"

START_URL = "https://www.google.com"

# Supported actions
SUPPORTED_ACTIONS = ["click", "navigate", "type", "scroll", "wait", "none", "ask", "tell"]