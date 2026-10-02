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
    """Captures the Chromium AXTree, reconstructs parent roles, and returns a flat matrix."""
    cdp_session = page.context.new_cdp_session(page)
    all_raw_nodes = []
    
    try:
        baseline = cdp_session.send("Accessibility.getFullAXTree")
        all_raw_nodes.extend(baseline.get("nodes", []))
    except Exception as e:
        print(f"[ENGINE WARNING] Initial snapshot failed: {str(e)}")
    
    try:
        page.mouse.move(0, 0)
    except Exception:
        pass
    
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
    """Formats the text matrix and streams routing selection instructions."""
    matrix_lines = []
    for idx, item in enumerate(action_matrix):
        matrix_lines.append(f"[{idx}] TYPE: {item['role'].upper()} | LABEL: '{item['name']}'")
    flat_matrix = "\n".join(matrix_lines)
    
    system_prompt = f"""
    You are an autonomous web routing compiler. Your goal is: '{global_goal}'
    Past Action History: 
    {history}
    
    CRITICAL CONSTRAINTS:
    1. If the action history logs confirm the objective has been completely executed, your action parameter MUST be 'DONE'.
    2. If you see a cookie banner, modal, or popup, prioritize clicking it to clear the screen.
    3. If the item you need is likely below the fold, use the 'scroll_down' action.
    4. If you need to reveal a dropdown menu, use the 'hover' action on its header.
    5. SEARCH TOOL: To find specific text on the page, use the 'search' action and put your query in 'type_value'. The matching layout indices will be returned in the next step's history.
    6. NEVER reuse indices from past actions in your history. The layout matrix changes every step. Always choose the correct target_index strictly from the CURRENT matrix provided below.
    
    Review the following available interactive layout tree checklist carefully:
    {flat_matrix}
    
    Determine the single optimal action to advance toward the goal.
    You must respond ONLY with a raw JSON block matching this exact format. Do not wrap in markdown code backticks:
    {{
        "reasoning": "State your logic for this step.",
        "action": "click", "type", "hover", "scroll_down", "search", or "DONE",
        "target_index": 0 (set to null if scrolling, searching, or DONE),
        "type_value": "text parameters to insert if action is type, text to find if action is search, otherwise null"
    }}
    """
    
    print("[TERMINAL] Dispatching compiled layout matrix to local model...")
    try:
        response = chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': system_prompt}])
        raw_output = response.message.content.strip()
        
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
        
    if action_type == "SCROLL_DOWN":
        print("[EXECUTING NATIVE TRIGGER]: Target Action: SCROLL_DOWN")
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(1000) 
        return "Successfully scrolled down the viewport."
        
    if action_type == "SEARCH":
        if not type_text:
            return "Failed: SEARCH action requires a text query in 'type_value'."
            
        print(f"[EXECUTING NATIVE TRIGGER]: Target Action: SEARCH | Query: '{type_text}'")
        matches = []
        for idx, item in enumerate(action_matrix):
            # Simple substring match (case-insensitive) against the active matrix
            if type_text.lower() in item["name"].lower():
                matches.append(f"Index [{idx}] ({item['role']})")
                
        if matches:
            return f"SEARCH RESULTS for '{type_text}': Found at {', '.join(matches)}. Use these indices in your next step."
        else:
            return f"SEARCH RESULTS for '{type_text}': No matching interactive elements found in the current layout."

    if target_idx is None or target_idx >= len(action_matrix):
        return "Failed: Selected index exists outside active layout grid limits."
        
    chosen_element = action_matrix[target_idx]
    role = chosen_element["role"]
    name = chosen_element["name"]
    
    clean_name = html.unescape(name)
    for char in ["http", "─", "›", "..."]:
        if char in clean_name:
            clean_name = clean_name.split(char)[0]
    clean_name = clean_name.strip()
    
    if not clean_name or len(clean_name) < 3:
        clean_name = name[:25]
        
    print(f"[EXECUTING NATIVE TRIGGER]: Target Action: {action_type} | Selected Node: {role.upper()} | Text Vector: '{clean_name}'")
    
    try:
        playwright_role = role if role != "searchbox" else "textbox"
        locator = page.get_by_role(playwright_role, name=clean_name, exact=False).first
        
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
            page.wait_for_timeout(500)
            return f"Successfully typed '{type_text}' into: '{clean_name}'"
            
        elif action_type == "CLICK":
            try:
                locator.evaluate("node => node.removeAttribute('target')")
            except Exception:
                pass 

            locator.click(force=True)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(500)
            return f"Successfully clicked element: '{clean_name}'"
            
        else:
            return f"Failed: Unrecognized action type '{action_type}'."
            
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
        page.wait_for_timeout(1000)
        
        max_steps = 50 
        
        for step in range(max_steps):
            print(f"\n--- ENTERING ROUTING CYCLE INDEX {step + 1} ---")
            
            with open(HISTORY_FILE, "r") as f:
                current_history_text = f.read()
                
            action_matrix = build_reconstructed_tree(page)
            
            with open(INVENTORY_FILE, "w") as f:
                json.dump(action_matrix, f, indent=4)
                
            decision = call_local_router(goal, action_matrix, current_history_text)
            
            if not decision:
                print("[TERMINAL] Execution failure during model output conversion pass. Retrying next loop.")
                continue
                
            print(f"[ROUTER SUMMARY]: {decision.get('reasoning', 'No reasoning provided.')}")
            
            execution_result = execute_matrix_action(page, decision, action_matrix)
            print(f"[STATUS]: {execution_result}")
            
            if "SUCCESS" in execution_result and decision.get("action", "").upper() == "DONE":
                print("\n[TERMINAL] Final goal status confirmed by runtime analyzer. Execution completed successfully.")
                break
                
            if len(page.context.pages) > 1:
                new_active_page = page.context.pages[-1]
                new_active_page.bring_to_front()
                
                for background_page in page.context.pages[:-1]:
                    try:
                        background_page.close()
                    except Exception:
                        pass
                        
                page = new_active_page
                
            log_entry = f"Step {step + 1} | Action Taken: {decision.get('action')} | Type Input/Query: {decision.get('type_value')} | Result: {execution_result}\n"
            with open(HISTORY_FILE, "a") as f:
                f.write(log_entry)
                
        print("\n[TERMINAL] Processing run target finished. Releasing active interface hooks.")
        browser.close()

if __name__ == "__main__":
    run_agent_workflow(
        url="https://www.ebay.com",
        goal="Search strictly for 'Nvidia RTX 4090'. After searching, filter the results to 'Auctions'. Finally, sort the page by 'Ending Soonest' and click on the first valid item."
    )