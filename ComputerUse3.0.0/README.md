# Website Scanner - Installation & Setup

## Quick Start

### 1. Install Dependencies
```bash
pip install playwright
playwright install chromium
```

### 2. Configure the Starting URL
Edit `website_scanner.py` and change this line at the top:
```python
START_URL = "https://example.com"
```

Change it to any website you want to scan, like:
```python
START_URL = "https://github.com"
START_URL = "https://google.com"
START_URL = "https://amazon.com"
```

### 3. Run the Program
```bash
python website_scanner.py
```

## What It Does

The program will:

1. **Launch a browser** - Opens Chromium (visible window)
2. **Navigate to the hardcoded URL** - Goes to your START_URL
3. **Extract all information**:
   - 🔘 Buttons (with ID labels and click-ability status)
   - 🔗 Links (with URLs)
   - 📝 Input Fields (text, password, email, etc.)
   - 📌 Headings (H1, H2, H3, etc.)
   - 📄 Text Blocks (paragraphs and main content)
   - 🖼️  Images (with alt text)
   - 📋 Form Elements (select dropdowns, textareas)

4. **Display results** - Prints organized info to console with clear labels
5. **Save to JSON** - Writes `extraction_results.json` with complete data

## Output Files

- **Console Output**: Shows summaries and first few items of each category
- **extraction_results.json**: Complete structured data about everything found

## Key Features

✅ **Labeled Elements** - Every button, link, input gets a unique ID (btn_0, link_5, etc.)
✅ **Visibility Check** - Tracks which elements are actually visible on the page
✅ **Interactivity Info** - Shows which buttons are clickable vs disabled
✅ **Comprehensive Extraction** - Gets all text, headings, images, forms
✅ **Async/Fast** - Uses async Playwright for efficient scraping
✅ **Foundation for Future** - Structured data ready for clicking/interaction logic

## Future Enhancement Ideas

Once you have the extracted data, you can:
- Click buttons programmatically using saved element IDs
- Fill and submit forms
- Navigate links
- Take screenshots of elements
- Log user interactions

