import time
from playwright.sync_api import sync_playwright

def parse_ax_tree(node):
    """Recursively parses the dynamic Chromium Accessibility Tree nodes."""
    elements = []
    
    role = node.get("role", {}).get("value", "") if isinstance(node.get("role"), dict) else node.get("role", "")
    name = node.get("name", {}).get("value", "").strip() if isinstance(node.get("name"), dict) else node.get("name", "")
    
    actionable_roles = ["button", "link", "searchbox", "combobox", "checkbox", "textbox", "menuitem"]
    
    if role in actionable_roles and name:
        if role in ["searchbox", "textbox", "combobox"]:
            elements.append(f"  - [INPUT FIELD] Fill out: '{name}'")
        elif role in ["button", "menuitem"]:
            elements.append(f"  - [CLICKABLE TRIGGER] Click button: '{name}'")
        elif role == "link":
            elements.append(f"  - [NAVIGATION PATH] Go to: '{name}'")
            
    if "children" in node:
        for child in node["children"]:
            elements.extend(parse_ax_tree(child))
            
    return elements

def build_accumulated_tree(page):
    """
    Sequentially hovers over only the top-level main menu elements, 
    preventing the cursor from getting trapped inside child sub-menus.
    """
    all_discovered_elements = []
    
    print("[System] Capturing baseline page state...")
    cdp_session = page.context.new_cdp_session(page)
    initial_ax = cdp_session.send("Accessibility.getFullAXTree")
    for node in initial_ax.get("nodes", []):
        all_discovered_elements.extend(parse_ax_tree(node))

    # --- CRITICAL SELECTOR FIX ---
    # We explicitly target the top-level list item links inside the main navigation bar.
    # By specifying "> a" or filtering out list elements that live inside an existing sub-menu,
    # we isolate the main headers (Our Impact, Programs & Grants, etc.)
    top_level_selectors = [
        "nav > ul > li > a",                  # Standard WordPress/HTML5 main nav paths
        ".menu-main-menu-container > ul > li > a", 
        "nav .menu-item-has-children > a",    # Targets main expandable parent blocks directly
        "header .main-menu > li > a"
    ]
    
    # Let's combine them to find the primary navigation headers
    combined_selector = ", ".join(top_level_selectors)
    nav_headers = page.query_selector_all(combined_selector)
    
    # Fallback: If the site uses a totally custom layout, grab header links but filter out deep ones
    if not nav_headers:
        print("[System Warning] Specific top-level selectors missed. Falling back to filtered list...")
        all_links = page.query_selector_all("nav a, header a")
        nav_headers = [link for link in all_links if not any(fluff in (link.get_attribute("class") or "") for fluff in ["sub-menu", "dropdown-item"])]

    print(f"[System] Discovered {len(nav_headers)} true top-level navigation headers.")
    print("[System] Executing sequential Hover-and-Snapshot accumulation...")
    
    hover_count = 0
    for header in nav_headers:
        try:
            text = header.inner_text().strip()
            if header.is_visible() and text and len(text) < 30:
                print(f"  ├─ Hovering over primary menu header item: '{text}'")
                
                # 1. Physically glide the mouse cursor to the main menu header block
                header.hover(timeout=1500)
                page.wait_for_timeout(400) # Give the layout animation time to expand fully
                
                # 2. Grab the live Accessibility Tree while the specific hover state is active
                mid_hover_ax = cdp_session.send("Accessibility.getFullAXTree")
                for node in mid_hover_ax.get("nodes", []):
                    all_discovered_elements.extend(parse_ax_tree(node))
                
                hover_count += 1
        except Exception as e:
            continue
            
    print(f"  └─ Successfully accumulated states across all {hover_count} primary categories.")
    page.mouse.move(0, 0) # Clear the mouse focus back to neutral coordinates
    return all_discovered_elements

def run_iwmf_perfect_mapper():
    target_url = "https://www.iwmf.org/"
    print(f"\n[System] Pointing engine toward target URL: {target_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        page.goto(target_url)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)
        
        # Run our cumulative capture matrix
        processed_tree = build_accumulated_tree(page)
        
        print("\n" + "="*80)
        print(f" 📑 ACCUMULATED HOVER DECISION TREE FOR: {target_url}")
        print("="*80)
        
        # Deduplicate results cleanly across all snapshot iterations
        seen = set()
        for item in processed_tree:
            if item not in seen:
                print(item)
                seen.add(item)
        print("="*80)
            
        input("\nPress Enter to close session tracking gracefully...")
        browser.close()

if __name__ == "__main__":
    run_iwmf_perfect_mapper()