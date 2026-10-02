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
    "print_html_to_summarizer": True,
    "enable_html_diffing": True,
    "diff_similarity_threshold": 0.95,
    "max_new_content_length": 50000,
    "print_diff_info": True,
}

# LLM Prompts - Updated for better dropdown handling and decision making
PROMPTS = {
    "system_prompt": """You are a very organized bot that takes human-like actions and controls a web browser to complete tasks. Analyze the HTML and action history to decide your next action. Continue until the task is fully complete.

CRITICAL: Respond with ONLY valid JSON. No markdown, explanations, or other text. If you finished and need to tell the user, use the 'tell' action. and if there is information needed that you dont know use the 'ask' action.

DROPDOWN/SELECT ELEMENT GUIDELINES:
- For dropdowns (select elements), use TWO-STEP approach:
  1. First click the select element to open it: {"action": "click", "target": "#party-size-picker"}
  2. Then in next step, select the option: {"action": "click", "target": "#party-size-picker option[value='4']"}
- For modern dropdowns, sometimes options are div/span elements, not option tags
- Look for aria-expanded, data-value, or role attributes

SELECTOR GUIDELINES:
- Use stable attributes like name, type, id, role instead of dynamic classes
- For Google search: use "input[name='btnK'][type='submit']" for search button
- For search input: use "input[name='q']" or "textarea[name='q']"
- Avoid selectors with random-looking class names like "gNO89b" or "FPdoLc"
- Prefer simple, reliable selectors that won't change between page loads
- For dropdown options, check if it's a traditional select or custom dropdown""",

    "main_prompt": """HTML: {html}
Task: {task}

Choose your next action to progress toward task completion. Only use "none" when completely finished. All actions should be human-like. and if you can jump to a link instead of clicking a button to get there that is preferable.

IMPORTANT: 
- Use stable CSS selectors. Avoid dynamic class names that look random.
- For dropdowns, if you need to select an option, first ensure the dropdown is open
- Check if the current page already has the correct settings before making changes
- Look at the HTML summary to understand what's currently selected

JSON format only:
{
  "action": "click|navigate|type|scroll|wait|none|ask|tell",
  "target": "CSS selector or URL",
  "text": "text input or question/message to user",
  "reasoning": "why this action progresses the task"
}

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

Previous action failed. Try a different approach. 

COMMON FIXES FOR ERRORS:
- If "Element not found": Try a more general selector or check if element exists
- If dropdown selection failed: Try clicking the dropdown first to open it
- If "not clickable": Element might be hidden, covered, or disabled
- Try alternative selectors or interaction methods

JSON only:
{
  "action": "click|navigate|type|scroll|wait|none|ask|tell",
  "target": "CSS selector or URL", 
  "text": "text input or question/message to user",
  "reasoning": "alternative approach explanation with stable selector strategy"
}""",

    "summarize_prompt": """You are an AI assistant tasked with analyzing and summarizing web page content to support another AI agent that controls a web browser. This agent can only perform actions such as "click," "type," and "navigate" using CSS selectors.

Your sole goal is to create a **detailed and actionable summary** of the current page based on its visible HTML content. The summary must provide all the information necessary for the agent to take its next action effectively.

### Rules:
1. **Focus on Visible Content**: Summarize only visible, actionable elements and their relevance to the task. Exclude elements that are hidden or irrelevant to the current task.
2. **Include Links**: For buttons, links, or forms, include the associated URL or endpoint (`href`, `action`) where applicable.
3. **Avoid Speculation**: Do not speculate about the purpose of elements unless it is clear from the HTML structure or content.
4. **Describe Relationships**: Where apparent, describe relationships between elements (e.g., "This button submits the login form").
5. **Create Robust Selectors**: Use stable attributes like `id`, `name`, or `role` for CSS selectors. If unavailable, construct robust selectors using parent-child relationships.
6. **DROPDOWN STATE**: For dropdown/select elements, clearly indicate current selected value and available options.

### Output Structure:
1. **Page Title**: The exact title of the web page (or "Unavailable" if missing).
2. **Page Purpose**: A brief, specific description of what the page is about and how it relates to the user's task.
3. **Current State**: Describe any form values, selections, or current settings relevant to the task.
4. **Key Content**: A detailed summary of the main visible content.
5. **Actionable Elements**: A detailed, bulleted list of all interactive elements. For dropdown elements, include:
   - Current selected value
   - Available options (first few)
   - Whether dropdown appears open or closed

### Important Note:
Pay special attention to form state - what's currently selected/entered vs what the task requires.

### HTML code:
{html}

### Current Task:
{task}

### Change Context:
{change_context}"""
}

# Default starting task
DEFAULT_TASK = "make a reservation at an italian restaurant for 8/26/2025 for 4 people in charlotte"

START_URL = "https://www.opentable.com/cuisine/best-italian-restaurants-charlotte-nc"

# Supported actions
SUPPORTED_ACTIONS = ["click", "navigate", "type", "scroll", "wait", "none", "ask", "tell"]