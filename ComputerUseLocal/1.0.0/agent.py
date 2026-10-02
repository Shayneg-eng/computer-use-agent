import os
import json
import time
import html
from playwright.sync_api import sync_playwright
from ollama import chat

# Memory Tracking and Architecture Configurations
MEMORY_DIR = "memory"
SESSION_FILE = os.path.join(MEMORY_DIR, "session_state.json")
INVENTORY_FILE = os.path.join(MEMORY_DIR, "page_inventory.json")
MODEL_NAME = "gemma4:e4b"

def init_system_memory(start_url, global_goal):
    """Resets storage files and builds baseline layout schema trackers."""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    session_data = {
        "start_url": start_url,
        "global_goal": global_goal,
        "history": [],
        "loop_count": 0
    }
    with open(SESSION_FILE, "w") as f:
        json.dump(session_data, f, indent=4)
    with open(INVENTORY_FILE, "w") as f:
        json.dump({}, f)

def parse_ax_node(node):
    """Extracts critical interactive element roles and browser parameters."""
    elements = []
    role = node.get("role", {}).get("value", "") if isinstance(node.get("role"), dict) else node.get("role", "")
    name = node.get("name", {}).get("value", "").strip() if isinstance(node.get("name"), dict) else node.get("name", "")
    node_id = node.get("nodeId")
    
    actionable_roles = ["button", "link", "searchbox", "combobox", "checkbox", "textbox", "listboxoption", "menuitem"]
    
    if role in actionable_roles and name and node_id:
        elements.append({
            "cdp_id": node_id,
            "role": role,
            "name": name
        })
    return elements

def build_reconstructed_tree(page):
    """
    Executes sequential hover-peeks across main layout categories, captures the 
    Chromium AXTree, reconstructs parent roles, and returns a flat, clean action matrix.
    """
    cdp_session = page.context.new_cdp_session(page)
    all_raw_nodes = []
    
    # 1. Baseline Capture
    try:
        baseline = cdp_session.send("Accessibility.getFullAXTree")
        all_raw_nodes.extend(baseline.get("nodes", []))
    except Exception as e:
        print(f"[ENGINE WARNING] Initial snapshot failed: {str(e)}")
    
    # 2. Look-Ahead Hover Sequence (Isolating Top-Level Structural Nav Nodes Only)
    nav_headers = page.query_selector_all("nav > ul > li > a, header .main-menu > li > a, nav .menu-item-has-children > a")
    if not nav_headers:
        nav_headers = page.query_selector_all("nav a, header a")
        
    hover_count = 0
    for header in nav_headers[:8]:  # Optimized boundary constraints to preserve clock cycles
        try:
            if header.is_visible() and len(header.inner_text().strip()) < 25:
                header.hover(timeout=1000)
                page.wait_for_timeout(300)  # Quick settling buffer for animation rendering
                hover_data = cdp_session.send("Accessibility.getFullAXTree")
                all_raw_nodes.extend(hover_data.get("nodes", []))
                hover_count += 1
        except Exception:
            continue
    try:
        page.mouse.move(0, 0)  # Return virtual cursor to neutral coordinate space
    except Exception:
        pass
    
    # 3. Two-Pass Parent Role Reconstruction
    node_directory = {node["nodeId"]: node for node in all_raw_nodes}
    deduplicated_actions = []
    seen_signatures = set()
    
    for node in all_raw_nodes:
        role = node.get("role", {}).get("value", "") if isinstance(node.get("role"), dict) else node.get("role", "")
        name = node.get("name", {}).get("value", "").strip() if isinstance(node.get("name"), dict) else node.get("name", "")
        node_id = node.get("nodeId")
        
        # Pull hidden text parameters from children up to input fields
        if role in ["combobox", "searchbox", "textbox"] and not name:
            for child_id in node.get("childIds", []):
                child = node_directory.get(child_id)
                if child:
                    c_name = child.get("name", {}).get("value", "").strip() if isinstance(child.get("name"), dict) else child.get("name", "")
                    c_val = child.get("value", {}).get("value", "").strip() if isinstance(child.get("value"), dict) else child.get("value", "")
                    name = c_name or c_val
                    if name: 
                        break
                    
        if name and node_id:
            sig = f"{role}||{name}"
            if sig not in seen_signatures:
                parsed = parse_ax_node(node)
                if parsed:
                    parsed[0]["name"] = name
                    deduplicated_actions.extend(parsed)
                    seen_signatures.add(sig)
                    
    return deduplicated_actions

def call_local_router(global_goal, action_matrix, history):
    """Formats the simplified plain text matrix and streams routing selection instructions to Gemma."""
    matrix_lines = []
    for idx, item in enumerate(action_matrix):
        matrix_lines.append(f"[{idx}] TYPE: {item['role'].upper()} | LABEL: '{item['name']}'")
    flat_matrix = "\n".join(matrix_lines)
    
    system_prompt = f"""
    You are an autonomous web routing compiler. Your goal is: '{global_goal}'
    Past Action History: {history}
    
    CRITICAL CONSTRAINT: If the action history logs confirm the objective has been completely executed 
    (e.g., product searched, targeted, and clicked to cart) and the current layout displays that state, 
    your action parameter MUST be 'DONE'.
    
    Review the following available interactive layout tree checklist carefully:
    {flat_matrix}
    
    Determine the single optimal index number needed to advance toward the goal.
    You must respond ONLY with a raw JSON block matching this exact format. Do not wrap in markdown code backticks:
    {{
        "reasoning": "State why this index matches the goal requirements, or why the goal is complete.",
        "action": "click" or "type" or "DONE",
        "target_index": 0,
        "type_value": "text parameters to insert if action is type, otherwise null"
    }}
    """
    
    print("[TERMINAL] Dispatching compiled layout matrix to local Gemma 4...")
    try:
        response = chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': system_prompt}])
        raw_output = response.message.content.strip()
        
        # Enforce strict raw JSON structure boundaries
        if "{" in raw_output:
            raw_output = raw_output[raw_output.find("{"):raw_output.rfind("}")+1]
            
        return json.loads(raw_output)
    except Exception as e:
        print(f"[TERMINAL ERROR] Failed to compute local model response parse structure: {str(e)}")
        return None

def execute_matrix_action(page, decision_block, action_matrix):
    """Resolves composite string layout anomalies and dispatches atomic browser events."""
    action_type = decision_block.get("action", "").upper()
    target_idx = decision_block.get("target_index")
    type_text = decision_block.get("type_value")
    
    if action_type == "DONE":
        return "SUCCESS: Target objective fulfilled. Halting active agent pipeline."
        
    if target_idx is None or target_idx >= len(action_matrix):
        return "Failed: Selected index exists outside active layout grid limits."
        
    chosen_element = action_matrix[target_idx]
    role = chosen_element["role"]
    name = chosen_element["name"]
    
    # --- DEFENSIVE SUBSTRING FILTER ENGINE ---
    # Convert character encoding anomalies (like &#39; into ') and remove composite URL weight
    clean_name = html.unescape(name)
    if "http" in clean_name:
        clean_name = clean_name.split("http")[0]
    if "─" in clean_name:
        clean_name = clean_name.split("─")[0]
    if "›" in clean_name:
        clean_name = clean_name.split("›")[0]
    if "..." in clean_name:
        clean_name = clean_name.split("...")[0]
    clean_name = clean_name.strip()
    
    # Low-limit recovery safety bounds
    if not clean_name or len(clean_name) < 3:
        clean_name = name[:25]
        
    print(f"[EXECUTING NATIVE TRIGGER]: Target Action: {action_type} | Selected Node: {role.upper()} | Text Vector: '{clean_name}'")
    
    try:
        if role in ["searchbox", "textbox", "combobox"]:
            selector = "input, textarea, [role='combobox']"
            elements = page.query_selector_all(selector)
            for el in elements:
                if el.is_visible() and (clean_name.lower() in (el.get_attribute("placeholder") or "").lower() or clean_name.lower() in (el.get_attribute("aria-label") or "").lower()):
                    el.fill(type_text if type_text else "")
                    el.press("Enter")
                    page.wait_for_load_state("domcontentloaded")
                    page.wait_for_timeout(2000)
                    return f"Successfully typed and entered values into field container: '{clean_name}'"
            return "Failed to isolate exact text field pointer configuration."
            
        else:
            # Dispatch event clicks directly to circumvent layout covers and floating flags
            locator = page.get_by_text(clean_name).first
            locator.dispatch_event("click")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)
            return f"Successfully dispatched click event sequence to element node: '{clean_name}'"
            
    except Exception as e:
        return f"Execution aborted via runtime driver exception: {str(e)}"

def run_agent_workflow(url, goal):
    """Orchestrates runtime state loops, memory logging controls, and exit states."""
    init_system_memory(url, goal)
    
    with sync_playwright() as p:
        print("[TERMINAL] Activating visible automation browser profile...")
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        print(f"[TERMINAL] Connecting to starting url context window: {url}")
        page.goto(url)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)
        
        max_steps = 4
        for step in range(max_steps):
            print(f"\n--- ENTERING ROUTING CYCLE INDEX {step + 1} ---")
            
            with open(SESSION_FILE, "r") as f:
                session = json.load(f)
                
            # Step 1: Compress page elements into clean interactive tree list matrix array
            action_matrix = build_reconstructed_tree(page)
            
            # Save matrix snapshot down to file directory for diagnostic trace logging
            with open(INVENTORY_FILE, "w") as f:
                json.dump(action_matrix, f, indent=4)
                
            # Step 2: Extract current path trajectory from the local model router
            decision = call_local_router(session["global_goal"], action_matrix, session["history"])
            if not decision:
                print("[TERMINAL] Execution failure during model output conversion pass. Breaking loop.")
                break
                
            print(f"[ROUTER SUMMARY]: {decision['reasoning']}")
            
            # Step 3: Run execution natively through target dispatch handlers
            execution_result = execute_matrix_action(page, decision, action_matrix)
            print(f"[STATUS]: {execution_result}")
            
            # Step 4: Verification check for agent exit metrics
            if "SUCCESS" in execution_result:
                print("\n[TERMINAL] Final goal status confirmed by runtime analyzer. Execution completed successfully.")
                break
                
            # Keep log registers up to date
            session["history"].append({
                "step": step + 1,
                "decision": decision,
                "result": execution_result
            })
            session["loop_count"] = step + 1
            with open(SESSION_FILE, "w") as f:
                json.dump(session, f, indent=4)
                
            time.sleep(1)
            
        print("\n[TERMINAL] Processing run target finished. Releasing active interface hooks.")
        browser.close()

if __name__ == "__main__":
    # E-Commerce Transaction Path Testing Suite
    run_agent_workflow(
        url="https://www.ebay.com",
        goal="go to see auctions and then look for an Nvidia RTX 4090 and click on one"
    )