import os
import json
import time
import html
from playwright.sync_api import sync_playwright
from ollama import chat

# Memory Tracking and Architecture Configurations
MEMORY_DIR = "memory"
HISTORY_FILE = os.path.join(MEMORY_DIR, "session_history.txt") 
INVENTORY_FILE = os.path.join(MEMORY_DIR, "page_inventory.json")
MODEL_NAME = "gemma4:e4b"

def init_system_memory(start_url, global_goal):
    """Resets storage files and builds baseline text trackers."""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    
    with open(HISTORY_FILE, "w") as f:
        f.write(f"START_URL: {start_url}\n")
        f.write(f"GLOBAL_GOAL: {global_goal}\n")
        f.write("--- ACTION LOG ---\n")
        
    with open(INVENTORY_FILE, "w") as f:
        json.dump({}, f)

def extract_page_text(page):
    """Grabs visible plain text from the DOM, avoiding heavy CSS computed style loops."""
    try:
        raw_text = page.evaluate("document.body.innerText")
        return raw_text[:4000] if raw_text else "No readable text found on current screen."
    except Exception as e:
        print(f"[ENGINE WARNING] Failed to extract page text: {str(e)}")
        return "Text extraction failed."

def generate_context_summary(page_text, global_goal, history):
    """Sub-agent dedicated to neutrally collapsing page state into relevant context."""
    system_prompt = f"""
    You are a neutral situational awareness analyzer. 
    
    GLOBAL GOAL: '{global_goal}'
    RECENT HISTORY: {history[-500:]}
    
    CURRENT PAGE RAW TEXT:
    {page_text}
    
    Write a concise, 2-3 sentence summary of what is currently on the screen that is relevant to the goal.
    DO NOT impart any direction or next steps. ONLY summarize the current state.
    """
    
    print("[TERMINAL] Calling Sub-Agent: Summarizer...")
    try:
        response = chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': system_prompt}])
        return response.message.content.strip()
    except Exception:
        return "Context summary unavailable."

def check_goal_completion(global_goal, history):
    """Evaluator sub-agent to strictly check if the goal is finished."""
    prompt = f"""
    GLOBAL GOAL: '{global_goal}'
    
    HISTORY:
    {history}
    
    Based on the history logs, has the global goal been completely executed? 
    Answer strictly with 'YES' or 'NO'. Do not explain.
    """
    print("[TERMINAL] Calling Sub-Agent: Evaluator...")
    try:
        response = chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
        return "YES" in response.message.content.upper()
    except Exception:
        return False

def generate_next_step_plan(global_goal, page_summary, history):
    """Planner sub-agent that predicts exactly ONE step into the future."""
    prompt = f"""
    You are the logic planner. 
    GLOBAL GOAL: '{global_goal}'
    CURRENT PAGE SUMMARY: {page_summary}
    HISTORY: {history[-800:]}
    
    CRITICAL CONSTRAINTS:
    1. If you see a cookie banner, modal, or popup, clearing it is your next step.
    2. DROPDOWNS ARE TWO STEPS: If the goal requires sorting (e.g., 'Ending soonest' or 'Lowest price'), you must FIRST plan to click the 'Sort' dropdown. On the VERY NEXT step, you must plan to click the specific sort option.
    3. VERIFY EXECUTION: Always read the 'Result:' of the last action in your HISTORY. If your previous plan was to click a specific option, but the result shows only a dropdown header (like 'Sort') was clicked, you MUST plan to click that specific option again in this step. Do not skip ahead.
    4. INFERRED SUCCESS: If your recent history shows you just typed credentials (like a password) and the current summary describes a normal homepage or feed, assume the login was successful. Move immediately to the next phase of the GLOBAL GOAL. Do not attempt to log in again.
    5. AVOID DEAD LOOPS: If the history shows the previous step resulted in "SEARCH RESULTS... No matches." for a specific button (like 'Log In'), that element no longer exists on the screen. Do not plan to click it again. Pivot to the next logical step to advance the goal.
    6. THE ESCAPE PROTOCOL: If you are searching for a general feed or list of items, but the current summary indicates you are trapped inside a single, specific post/item page (e.g., a single event promotion, a specific discussion thread, an ad), DO NOT SCROLL. Your immediate next step MUST be to plan to click the site's main logo, a 'Home' button, or a 'Back' button to escape the single post and return to the main feed.
    
    What is the single, immediate next step required? State ONLY ONE action into the future in plain text (e.g., 'Type Nvidia into the search bar', 'Click the Auctions filter', 'Click the Sort dropdown', 'Click the Ending Soonest option', 'Click the Reddit logo to return home').
    """
    print("[TERMINAL] Calling Sub-Agent: Planner...")
    try:
        response = chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
        return response.message.content.strip()
    except Exception:
        return "Scroll down to reveal more options."

def filter_element_roles(plan):
    """Filter sub-agent to select HTML roles relevant to the planner's decision."""
    prompt = f"""
    PLAN: '{plan}'
    
    Which HTML roles are needed to execute this plan? Choose strictly from this list:
    button, link, searchbox, combobox, checkbox, textbox, listboxoption, menuitem
    
    Respond ONLY with a comma-separated list of the relevant roles. If the plan is to scroll or search the page text, or if you are unsure, output 'all'.
    """
    print("[TERMINAL] Calling Sub-Agent: Role Filter...")
    try:
        response = chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}]).message.content.lower()
        if "all" in response:
            return ["button", "link", "searchbox", "combobox", "checkbox", "textbox", "listboxoption", "menuitem"]
        return [role.strip() for role in response.split(",") if role.strip() in ["button", "link", "searchbox", "combobox", "checkbox", "textbox", "listboxoption", "menuitem"]]
    except Exception:
        return ["button", "link", "searchbox", "combobox", "checkbox", "textbox", "listboxoption", "menuitem"]

def format_action_json(plan, filtered_matrix):
    """Formatter sub-agent to rigidly output JSON without thinking about the larger goal."""
    matrix_lines = []
    for item in filtered_matrix:
        matrix_lines.append(f"[{item['original_index']}] TYPE: {item['role'].upper()} | LABEL: '{item['name']}'")
    flat_matrix = "\n".join(matrix_lines)
    
    prompt = f"""
    You are a strict JSON formatter. 
    
    YOUR PLAN: '{plan}'
    
    AVAILABLE ELEMENTS:
    {flat_matrix}
    
    CRITICAL CONSTRAINTS:
    1. Choose your action from: "click", "type", "hover", "scroll_down", or "search".
    2. "search" is a find-in-page native tool to scan for plain text. 
    3. "type" is for typing into physical search bars or textboxes. You MUST provide the text in 'type_value'.
    4. Select the exact bracketed number (e.g., 5 from [5]) as the 'target_index'.
    
    Respond ONLY with a raw JSON block matching this exact format:
    {{
        "reasoning": "Briefly state why this index/action matches the plan.",
        "action": "click|type|hover|scroll_down|search",
        "target_index": 0 (set to null if scrolling or searching),
        "type_value": "text to type or search (or null)"
    }}
    """
    print("[TERMINAL] Calling Sub-Agent: JSON Formatter...")
    try:
        response = chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
        raw_output = response.message.content.strip()
        if "{" in raw_output:
            raw_output = raw_output[raw_output.find("{"):raw_output.rfind("}")+1]
        return json.loads(raw_output)
    except Exception as e:
        print(f"[FORMATTER ERROR] Syntax parsing failed: {str(e)}")
        return None

def parse_ax_node(node):
    elements = []
    role = node.get("role", {}).get("value", "") if isinstance(node.get("role"), dict) else node.get("role", "")
    name = node.get("name", {}).get("value", "").strip() if isinstance(node.get("name"), dict) else node.get("name", "")
    node_id = node.get("nodeId")
    
    actionable_roles = ["button", "link", "searchbox", "combobox", "checkbox", "textbox", "listboxoption", "menuitem"]
    if role in actionable_roles and name and node_id:
        elements.append({"cdp_id": node_id, "role": role, "name": name})
    return elements

def build_reconstructed_tree(page):
    cdp_session = page.context.new_cdp_session(page)
    all_raw_nodes = []
    
    try:
        baseline = cdp_session.send("Accessibility.getFullAXTree")
        all_raw_nodes.extend(baseline.get("nodes", []))
    except Exception: pass
    try: page.mouse.move(0, 0)
    except Exception: pass
    
    node_directory = {node["nodeId"]: node for node in all_raw_nodes}
    deduplicated_actions = []
    seen_signatures = set()
    
    for node in all_raw_nodes:
        role = node.get("role", {}).get("value", "") if isinstance(node.get("role"), dict) else node.get("role", "")
        name = node.get("name", {}).get("value", "").strip() if isinstance(node.get("name"), dict) else node.get("name", "")
        node_id = node.get("nodeId")
        
        if role in ["combobox", "searchbox", "textbox"] and not name:
            for child_id in node.get("childIds", []):
                child = node_directory.get(child_id)
                if child:
                    c_name = child.get("name", {}).get("value", "").strip() if isinstance(child.get("name"), dict) else child.get("name", "")
                    c_val = child.get("value", {}).get("value", "").strip() if isinstance(child.get("value"), dict) else child.get("value", "")
                    name = c_name or c_val
                    if name: break
                    
        if name and node_id:
            sig = f"{role}||{name}"
            if sig not in seen_signatures:
                parsed = parse_ax_node(node)
                if parsed:
                    parsed[0]["name"] = name
                    deduplicated_actions.extend(parsed)
                    seen_signatures.add(sig)
                    
    return deduplicated_actions

def execute_matrix_action(page, decision_block, action_matrix):
    """Resolves composite string layout anomalies and dispatches atomic browser events."""
    action_type = decision_block.get("action", "").upper()
    target_idx = decision_block.get("target_index")
    type_text = decision_block.get("type_value")
        
    if action_type == "SCROLL_DOWN":
        print("[EXECUTING NATIVE TRIGGER]: Target Action: SCROLL_DOWN")
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(1000) 
        return "Successfully scrolled down the viewport."
        
    if action_type == "SEARCH":
        if not type_text: 
            return "Failed: SEARCH action requires a text query."
        print(f"[EXECUTING NATIVE TRIGGER]: Target Action: SEARCH | Query: '{type_text}'")
        matches = [f"Index [{idx}] ({item['role']})" for idx, item in enumerate(action_matrix) if type_text.lower() in item["name"].lower()]
        return f"SEARCH RESULTS for '{type_text}': Found at {', '.join(matches)}." if matches else f"SEARCH RESULTS for '{type_text}': No matches."

    if target_idx is None or target_idx >= len(action_matrix):
        return "Failed: Selected index exists outside active layout grid limits."
        
    chosen_element = action_matrix[target_idx]
    role = chosen_element["role"]
    name = chosen_element["name"]
    clean_name = html.unescape(name).split("─")[0].strip()
    clean_name = clean_name if len(clean_name) >= 3 else name[:25]
        
    print(f"[EXECUTING NATIVE TRIGGER]: Target Action: {action_type} | Selected Node: {role.upper()} | Text Vector: '{clean_name}'")
    
    try:
        locator = page.get_by_role(role if role != "searchbox" else "textbox", name=clean_name, exact=False).first
        if not locator.is_visible():
            locator = page.locator(f"text='{clean_name}'").first
            
        if action_type == "HOVER":
            locator.hover(force=True)
            page.wait_for_timeout(1000)
            return f"Successfully hovered over element: '{clean_name}'"
            
        elif action_type == "TYPE":
            locator.fill(type_text if type_text else "", force=True)
            locator.press("Enter")
            page.wait_for_load_state("domcontentloaded")
            return f"Successfully typed '{type_text}' into: '{clean_name}'"
            
        elif action_type == "CLICK":
            locator.evaluate("node => node.removeAttribute('target')") # prevent new tabs
            locator.click(force=True)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000) # Let modals/dropdowns render to avoid blindspots
            return f"Successfully clicked element: '{clean_name}'"
            
        else:
            return f"Failed: Unrecognized action type '{action_type}'."
            
    except Exception as e:
        return f"Execution aborted via runtime driver exception: {str(e)}"

def run_agent_workflow(url, goal):
    init_system_memory(url, goal)
    
    with sync_playwright() as p:
        print("[TERMINAL] Activating visible automation browser profile...")
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        page.goto(url)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)
        
        max_steps = 20 
        
        for step in range(max_steps):
            print(f"\n--- ENTERING ROUTING CYCLE INDEX {step + 1} ---")
            
            with open(HISTORY_FILE, "r") as f:
                current_history_text = f.read()
                
            # Phase 1: Evaluate Completion
            is_done = check_goal_completion(goal, current_history_text)
            if is_done:
                print("[STATUS]: SUCCESS: Target objective fulfilled. Halting active agent pipeline.")
                break
                
            # Phase 2: Context Extraction & Summary
            raw_page_text = extract_page_text(page)
            page_summary = generate_context_summary(raw_page_text, goal, current_history_text)
            print(f"[SUMMARY]: {page_summary}")
            
            # Phase 3: The Planner
            plan = generate_next_step_plan(goal, page_summary, current_history_text)
            print(f"[PLANNER]: {plan}")
            
            # Phase 4: Role Filter
            allowed_roles = filter_element_roles(plan)
            print(f"[FILTER]: Proceeding with roles: {allowed_roles}")
            
            # Matrix Construction & Python Filtering
            action_matrix = build_reconstructed_tree(page)
            for idx, item in enumerate(action_matrix):
                item["original_index"] = idx  # Preserve absolute index for execution
                
            filtered_matrix = [item for item in action_matrix if item["role"] in allowed_roles]
            if len(filtered_matrix) == 0: 
                filtered_matrix = action_matrix # Safe fallback if filter was too strict
            
            # Phase 5: JSON Formatter
            decision = format_action_json(plan, filtered_matrix)
            if not decision:
                continue
                
            print(f"[FORMATTER]: {decision.get('reasoning', 'No reasoning provided.')}")
            
            # Phase 6: Execution Loop
            execution_result = execute_matrix_action(page, decision, action_matrix)
            print(f"[STATUS]: {execution_result}")
            
            if len(page.context.pages) > 1:
                new_active_page = page.context.pages[-1]
                new_active_page.bring_to_front()
                for background_page in page.context.pages[:-1]:
                    try: background_page.close()
                    except: pass
                page = new_active_page
                
            log_entry = f"Step {step + 1} | Plan: {plan} | Action Taken: {decision.get('action')} | Target/Query: {decision.get('type_value') or decision.get('target_index')} | Result: {execution_result}\n"
            with open(HISTORY_FILE, "a") as f:
                f.write(log_entry)
                
        print("\n[TERMINAL] Processing run target finished.")
        browser.close()

if __name__ == "__main__":
    run_agent_workflow(
        url="https://www.reddit.com",
        goal="Login to reddit using my account. Use the email address '<REDDIT_EMAIL>' and the password '<REDDIT_PASSWORD>'"
    )