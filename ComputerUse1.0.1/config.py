import os
# Configuration file for Computer Use AI

# LLM Configuration
LLM_CONFIG = {
    "poe": {
        "api_key": os.getenv("POE_API_KEY", ""),
        "base_url": "https://api.poe.com/v1",
        "model": "GPT-OSS-120B-T",
        "max_tokens": 8192,
        "temperature": 0.1
    },
    "deepseek": {
        "api_key": os.environ["DEEPSEEK_API_KEY"],
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "max_tokens": 8192,
        "temperature": 0.1
    }
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
    "llm_provider": "deepseek", # Poe or DeepSeek
    "max_steps": 100,
    "html_truncate_length": 100000,
    "screenshot_on_error": True,
    "log_level": "INFO",
    "history_context_limit": None,
    "history_summary_recent": 25,
    "human_like_delays": True,
    "min_delay": 3,
    "max_delay": 6,
    "check_captcha": False,
    "print_processed_html": True,
    "print_html_to_summarizer": True
}

# LLM Prompts
PROMPTS = {
    "system_prompt": """You are a very organized bot that takes human-like actions and controls a web browser to complete tasks. Analyze the HTML and action history to decide your next action. Continue until the task is fully complete.

CRITICAL: Respond with ONLY valid JSON. No markdown, explanations, or other text. If you finished and need to tell the user, use the 'tell' action. and if there is information needed that you dont know use the 'ask' action.

SELECTOR GUIDELINES:
- Use stable attributes like name, type, id, role instead of dynamic classes
- For Google search: use "input[name='btnK'][type='submit']" for search button
- For search input: use "input[name='q']" or "textarea[name='q']"
- Avoid selectors with random-looking class names like "gNO89b" or "FPdoLc"
- Prefer simple, reliable selectors that won't change between page loads""",

    "main_prompt": """HTML: {html}
Task: {task}

Choose your next action to progress toward task completion. Only use "none" when completely finished. All actions should be human-like.

IMPORTANT: Use stable CSS selectors. Avoid dynamic class names that look random.

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

Previous action failed. Try a different approach. Use stable selectors without dynamic classes.

JSON only:
{{
  "action": "click|navigate|type|scroll|wait|none|ask|tell",
  "target": "CSS selector or URL",
  "text": "text input or question/message to user",
  "reasoning": "alternative approach explanation with stable selector strategy"
}}""",

    "summarize_prompt": """You are an AI assistant tasked with analyzing and summarizing web page content to support another AI agent that controls a web browser. This agent can only perform actions such as "click," "type," and "navigate" using CSS selectors.

Your sole goal is to create a concise, factual summary of the current page based on its visible HTML content. The summary must provide only the information necessary for the agent to take its next action effectively.

### Rules:
1. Do not include details about features or elements that require external input methods the agent cannot use (e.g., voice search, image search).
2. Do not speculate about the purpose of elements unless it is clear from the HTML.
3. Exclude irrelevant or inaccessible elements, such as those unrelated to the user's task or hidden from view.
4. Focus exclusively on visible, actionable elements and their relevance to the task.

Your output should be structured as follows:

1. **Page Title**: The exact title of the web page.
2. **Page Purpose**: A brief, high-level description of what the page is about and how it relates to the user's task.
3. **Key Content**: A summary of the main visible text and relevant visual elements on the page.
4. **Actionable Elements**: A detailed, bulleted list of all interactive elements the agent can use. For each element, include:
   * **Label**: A clear, concise label describing the element (e.g., "Search button", "Login field").
   * **Purpose**: The function of the element on the page.
   * **Selector**: The most reliable CSS selector to uniquely identify the element. Use stable attributes like name, type, id, or role. Avoid dynamic or unpredictable class names.

### Important Note
The summary must be as concise and focused as possible. Include only information directly relevant to the agent's task and omit any extraneous details or context. Exclude elements or features that reference capabilities the agent cannot use (e.g., voice search, image search, or other non-clickable elements).

### HTML code:
{html}

### Current Task:
{task}

Summary:"""
}

# Default starting task
DEFAULT_TASK = "make a reservation at an italian restaurant for 8/26/2025 for 4 people in charlotte"

START_URL = "https://www.google.com"

# Supported actions
SUPPORTED_ACTIONS = ["click", "navigate", "type", "scroll", "wait", "none", "ask", "tell"]