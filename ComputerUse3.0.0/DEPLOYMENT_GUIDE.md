# Deployment & Setup Guide

## Final Directory Structure

```
ComputerUse3.0.0/
├── 📁 scanner/
│   ├── __init__.py
│   └── website_scanner.py         # Core: Playwright-based page extraction
│
├── 📁 search/
│   ├── __init__.py
│   └── smart_search.py            # Core: Text-based page element search
│
├── 📁 llm/
│   ├── __init__.py
│   └── ollama_agent.py            # Core: Ollama LLM integration & orchestration
│
├── 📁 utils/
│   ├── __init__.py
│   └── page_info_manager.py       # Utility: High-level page data access
│
├── 📁 current_page_information/   # Auto-generated runtime data
│   ├── buttons/                   # Extracted button elements
│   ├── links/                     # Extracted link elements
│   ├── input_fields/              # Extracted form inputs
│   ├── form_elements/             # Dropdowns, textareas, selects
│   ├── images/                    # Extracted images
│   ├── text_blocks/               # Text content blocks
│   ├── headings/                  # Page headings
│   ├── page_metadata/             # Page-level metadata
│   └── interactive_elements_index/ # Master index
│
├── main.py                        # Entry point: Orchestration & CLI
├── README.md                      # User documentation
├── requirements.txt               # Python dependencies
└── DEPLOYMENT_GUIDE.md           # This file
```

## Installation Steps

### 1. Install Python Dependencies
```bash
cd "c:\Coding\Code\Computer Use\ComputerUse3.0.0"
pip install -r requirements.txt
playwright install chromium
```

### 2. Verify Ollama is Running
```bash
# In a separate terminal/command prompt
ollama run qwen

# The qwen model should be downloaded and running
# (keep this terminal open while using the system)
```

### 3. Test the System
```bash
# Quick test - interactive mode
python main.py

# Type: scan https://example.com
# Then ask: What buttons are on this page?
# Type: quit to exit
```

## Module Overview

### scanner/website_scanner.py
**Purpose**: Extract all page elements using Playwright
**Key Features**:
- Async extraction with parallel processing
- CSS selector generation
- Bounding box calculation
- Accessibility attribute capture
- Form context linking
- Organized JSON output to `current_page_information/`

**Main Class**: `WebsiteScanner`
```python
from scanner import WebsiteScanner
scanner = WebsiteScanner()
await scanner.scan_website("https://example.com")
```

### search/smart_search.py
**Purpose**: Text-based search across extracted page elements
**Key Features**:
- No embeddings (pure string matching)
- Category-specific search methods
- Index-first approach for speed
- Returns structured results with IDs and selectors

**Main Class**: `SmartSearch`
```python
from search import SmartSearch
buttons = SmartSearch.search_buttons("login")
links = SmartSearch.search_links("home")
```

### llm/ollama_agent.py
**Purpose**: LLM integration for autonomous decision-making
**Key Features**:
- Ollama connection management
- Conversation history tracking
- Tool calling (search, scan)
- Autonomous loop execution
- System prompt with available functions

**Main Class**: `OllamaLLMAgent`
```python
from llm import OllamaLLMAgent
agent = OllamaLLMAgent(model="qwen")
await agent.scan_page("https://example.com")
await agent.chat("Find the login button")
```

### utils/page_info_manager.py
**Purpose**: High-level API for page information access
**Key Features**:
- Quick lookups by ID or text
- Page statistics retrieval
- Title and URL access
- Simplified data access patterns

**Main Class**: `PageInfoManager`
```python
from utils import PageInfoManager
buttons = PageInfoManager.get_all_buttons()
title = PageInfoManager.get_page_title()
```

## Usage Patterns

### Pattern 1: Interactive Chat
```bash
python main.py
# Then use commands: scan, goal, or ask questions freely
```

### Pattern 2: Single Page Analysis
```bash
python main.py scan https://example.com
```

### Pattern 3: Autonomous Task
```bash
python main.py task https://example.com "Find the sign-up button and list its location"
```

### Pattern 4: Custom Python Script
```python
import asyncio
from llm import OllamaLLMAgent

async def my_automation():
    agent = OllamaLLMAgent(model="qwen")
    
    # Scan a page
    await agent.scan_page("https://example.com")
    
    # Ask agent to find something
    response = await agent.chat("Find all form fields on this page")
    
    # Run autonomous loop
    await agent.run_autonomous_loop("Complete the sign-up form", max_iterations=5)

asyncio.run(my_automation())
```

## Data Flow

```
User Request
    ↓
main.py (entry point)
    ↓
OllamaLLMAgent (llm/ollama_agent.py)
    ├── Calls scanner.scan_website()
    ├── Stores in current_page_information/
    ├── Uses SmartSearch for queries
    └── Communicates with Ollama
         ↓
WebsiteScanner (scanner/website_scanner.py)
    ├── Launches Playwright browser
    ├── Extracts all elements (buttons, links, inputs, etc.)
    ├── Calculates CSS selectors & bounds
    └── Saves organized JSON
         ↓
current_page_information/ (folder structure)
    ├── buttons/, links/, inputs/, etc.
    ├── _index.json (quick lookup)
    └── _master_index.json (overview)
         ↓
SmartSearch (search/smart_search.py)
    └── Returns filtered, ranked results
         ↓
OllamaLLMAgent
    └── Formats results for LLM
         ↓
Ollama (local qwen model)
    └── Generates response/decision
         ↓
User
```

## Configuration

### Change Default URL
Edit [scanner/website_scanner.py](scanner/website_scanner.py#L08):
```python
START_URL = "https://your-site.com"
```

### Use Different Ollama Model
```python
agent = OllamaLLMAgent(model="llama2")  # or "neural-chat", "orca-mini", etc.
```

### Custom Ollama URL
```python
agent = OllamaLLMAgent(
    model="qwen",
    base_url="http://192.168.1.100:11434"  # Custom host
)
```

### Adjust Extraction Timeout
Edit [scanner/website_scanner.py](scanner/website_scanner.py#L170):
```python
await page.goto(url, wait_until="load", timeout=30000)  # 30 seconds
```

## Performance Optimization

### For Faster Extraction
- Headless mode is enabled (automatic)
- Parallel extraction is used (automatic)
- Network wait is set to "load" not "networkidle" (automatic)

### Search Speed
- Indexes are loaded first (automatic)
- Full files only loaded when needed (automatic)
- No embeddings overhead (automatic)

## Troubleshooting

### ❌ "Cannot connect to Ollama"
```bash
# Make sure Ollama is running and accessible
ollama serve  # Windows: just type "ollama" if installed globally
# Check it's listening on http://localhost:11434
```

### ❌ "No module named 'playwright'"
```bash
pip install playwright
playwright install chromium
```

### ❌ "Page not scanning properly"
- Check URL is accessible in your browser
- Verify no popup blockers or authentication required
- Increase timeout in websit_scanner.py

### ❌ "Empty search results"
- Run `scan <url>` first
- Check `current_page_information/` folder was created
- Verify page contains elements you're searching for

## Advanced Usage

### Create Custom Automation Script
```python
import asyncio
from llm import OllamaLLMAgent
from search import SmartSearch

async def find_and_click_login():
    agent = OllamaLLMAgent()
    await agent.scan_page("https://example.com")
    
    # Search for login button
    buttons = SmartSearch.search_buttons("login")
    if buttons:
        btn = buttons[0]
        print(f"Found: {btn['text']}")
        print(f"Selector: {btn['selector']}")
        print(f"Bounds: {btn['bounds']}")
        # TODO: Click using Playwright
    
asyncio.run(find_and_click_login())
```

### Monitor Extraction Progress
Check `current_page_information/` folder during/after scan:
```powershell
# In PowerShell
Get-ChildItem "current_page_information" -Recurse | Measure-Object | Select-Object Count

# Watch folder grow in real-time
while($true) { 
    ls current_page_information -r | Measure-Object | Select-Object Count
    sleep 1
}
```

### Analyze Page Structure
```python
from search import SmartSearch
from utils import PageInfoManager

overview = SmartSearch.get_page_overview()
print(f"URL: {overview['page_url']}")
print(f"Title: {overview['title']}")
print(f"Buttons: {overview['summary']['total_buttons']}")
print(f"Links: {overview['summary']['total_links']}")
print(f"Forms: {overview['summary']['total_form_elements']}")
```

## Next Steps

1. ✅ Run interactive mode: `python main.py`
2. ✅ Test scanning: `scan https://example.com`
3. ✅ Ask questions: Ask the agent about page content
4. ✅ Run autonomous tasks: `goal "Find and analyze the contact form"`
5. Create custom scripts for your specific use cases

## Support & Issues

For issues with:
- **Playwright**: Check browser compatibility, popup blockers, authentication
- **Ollama**: Ensure service is running and model is downloaded
- **Module imports**: Verify Python path includes the workspace root

## Related Files

- [README.md](README.md) - User documentation
- [scanner/website_scanner.py](scanner/website_scanner.py) - Extraction logic
- [search/smart_search.py](search/smart_search.py) - Search implementation
- [llm/ollama_agent.py](llm/ollama_agent.py) - LLM integration
- [main.py](main.py) - Entry point and orchestration
