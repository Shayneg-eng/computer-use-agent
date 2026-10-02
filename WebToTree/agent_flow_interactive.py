import os
import json
import time
import html
from playwright.sync_api import sync_playwright
from ollama import chat

# Tracking Configurations
MEMORY_DIR = "memory"
SESSION_FILE = os.path.join(MEMORY_DIR, "session_state.json")
INVENTORY_FILE = os.path.join(MEMORY_DIR, "page_inventory.json")
VAULT_FILE = os.path.join(MEMORY_DIR, "user_vault.json")
MODEL_NAME = "gemma4:e4b"

def init_system_memory(start_url, global_goal):
    """Resets memory logging structures and ensures vault exists."""
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
        
    # Generate an empty boilerplate vault structure if none exists on disk
    if not os.path.exists(VAULT_FILE):
        default_vault = {"first_name": "", "email": "", "zip_code": ""}
        with open(VAULT_FILE, "w") as f:
            json.dump(default_vault, f, indent=4)

def load_user_vault():
    """Loads static credentials from local file asset safely."""
    try:
        with open(VAULT_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def parse_ax_node(node):
    """Extracts structural role parameters out of raw CDP lines."""
    elements = []
    role = node.get("role", {}).get("value", "") if isinstance(node.get("role"), dict) else node.get("role", "")
    name = node.get("name", {}).get("value", "").strip() if isinstance(node.get("name"), dict) else node.get("name", "")
    node_id = node.get("nodeId")
    
    actionable_roles = ["button", "link", "searchbox", "combobox", "checkbox", "textbox", "listboxoption", "menuitem"]
    
    if role in actionable_roles and name and node_id:
        elements.append({"cdp_id": node_id, "role": role, "name": name})
    return elements

def build_reconstructed_tree(page):
    """Gathers open elements, binds parents, and generates a clean flat matrix."""
    cdp_session = page.context.new_cdp_session(page)
    all_raw_nodes = []
    
    try:
        baseline = cdp_session.send("Accessibility.getFullAXTree")
        all_raw_nodes.extend(baseline.get("nodes", []))
    except Exception:
        pass
        
    nav_headers = page.query_selector_all("nav > ul > li > a, header .main-menu > li > a, nav .menu-item-has-children > a")
    if not nav_headers:
        nav_headers = page.query_selector_all("nav a, header a")
        
    for header in nav_headers[:6]:
        try:
            if header.is_visible() and len(header.inner_text().strip()) < 25:
                header.hover(timeout=1000)
                page.wait_for_timeout(200)
                hover_data = cdp_session.send("Accessibility.getFullAXTree")
                all_raw_nodes.extend(hover_data.get("nodes", []))
        except Exception:
            continue
            
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

def call_local_router(global_goal, action_matrix, history, vault_data):
    """Provides vault values and interaction rules to the model routing logic."""
    matrix_lines = []
    for idx, item in enumerate(action_matrix):
        matrix_lines.append(f"[{idx}] TYPE: {item['role'].upper()} | LABEL: '{item['name']}'")
    flat_matrix = "\n".join(matrix_lines)
    
    system_prompt = f"""
    You are an autonomous web routing compiler. Your goal is: '{global_goal}'
    Past Action History: {history}
    
    --- SAFE PRE-SAVED USER VAULT DATA ---
    Use these values directly if an input field requires them. Do not prompt the user for items listed here:
    {json.dumps(vault_data, indent=2)}
    
    --- INTERACTION PROTOCOL ---
    1. If the required data is in the User Vault, choose 'type' and fill it in using that value.
    2. If you must fill a field (e.g., password, dynamic prompt, account info) that is completely missing from both the vault and page history, you MUST set your action to 'ASK_USER'.
    3. If the objective is complete, set your action to 'DONE'.
    
    Available Interactive Layout Options:
    {flat_matrix}
    
    Respond ONLY with a raw JSON block matching this exact schema layout:
    {{
        "reasoning": "Explain your choice using vault checks or action matching requirements",
        "action": "click" or "type" or "ASK_USER" or "DONE",
        "target_index": 0,
        "type_value": "The literal text value string to enter if action is type, otherwise null",
        "question": "If action is ASK_USER, phrase your exact question to the human here, otherwise null"
    }}
    """
    
    print("[TERMINAL] Dispatching operational layout matrix to local Gemma 4...")
    try:
        response = chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': system_prompt}])
        raw_output = response.message.content.strip()
        if "{" in raw_output:
            raw_output = raw_output[raw_output.find("{"):raw_output.rfind("}")+1]
        return json.loads(raw_output)
    except Exception as e:
        print(f"[TERMINAL ERROR] Router response parse processing hit an anomaly: {str(e)}")
        return None

def execute_matrix_action(page, decision_block, action_matrix):
    """Processes native tool scripts, intercepting ASK_USER commands to query the shell console."""
    action_type = decision_block.get("action", "").upper()
    target_idx = decision_block.get("target_index")
    type_text = decision_block.get("type_value")
    
    if action_type == "DONE":
        return "SUCCESS: Target objective reached."
        
    # --- INTERACTIVE HUMANS-IN-THE-LOOP INTERCEPT TRIGGER ---
    if action_type == "ASK_USER":
        question = decision_block.get("question", "Please provide the missing data required for this input field context.")
        print(f"\n📢 [AI INTERACTIVE ENGINE REQUEST]: {question}")
        # Pause runtime execution thread and prompt terminal input capture safely
        human_response = input("⌨️ Enter response data string: ").strip()
        return f"HUMAN_RESPONSE_PROVIDED: User explicitly specified: '{human_response}'"
        
    if target_idx is None or target_idx >= len(action_matrix):
        return "Failed: Target index bounds mismatch."
        
    chosen_element = action_matrix[target_idx]
    role = chosen_element["role"]
    name = chosen_element["name"]
    
    clean_name = html.unescape(name)
    if "http" in clean_name: clean_name = clean_name.split("http")[0]
    if "›" in clean_name: clean_name = clean_name.split("›")[0]
    if "..." in clean_name: clean_name = clean_name.split("...")[0]
    clean_name = clean_name.strip()
    if not clean_name: clean_name = name[:20]
    
    print(f"[EXECUTING NATIVE TRIGGER]: Action: {action_type} | Node: {role.upper()} | Value: '{clean_name}'")
    
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
                    return f"Successfully typed values into input text field matching: '{clean_name}'"
            return "Failed to establish clear visibility handle matching target text box descriptor entries."
        else:
            locator = page.get_by_text(clean_name).first
            locator.dispatch_event("click")
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)
            return f"Successfully dispatched click event sequence to target element node: '{clean_name}'"
    except Exception as e:
        return f"Execution tracking aborted via structural interface fault: {str(e)}"

def run_agent_workflow(url, goal):
    """Manages continuous task loops, loading vault inputs, and collecting user feedback."""
    init_system_memory(url, goal)
    vault_data = load_user_vault()
    
    with sync_playwright() as p:
        print("[TERMINAL] Activating visible browser profile framework...")
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        print(f"[TERMINAL] Connecting initialization baseline to URL: {url}")
        page.goto(url)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)
        
        max_steps = 5
        for step in range(max_steps):
            print(f"\n--- ENTERING ROUTING CYCLE INDEX {step + 1} ---")
            
            with open(SESSION_FILE, "r") as f:
                session = json.load(f)
                
            action_matrix = build_reconstructed_tree(page)
            with open(INVENTORY_FILE, "w") as f:
                json.dump(action_matrix, f, indent=4)
                
            # Run router call passing vault items as system parameters
            decision = call_local_router(session["global_goal"], action_matrix, session["history"], vault_data)
            if not decision:
                print("[TERMINAL] Context parsing processing failed. Ending operational sequence loop.")
                break
                
            print(f"[ROUTER SUMMARY]: {decision['reasoning']}")
            
            execution_result = execute_matrix_action(page, decision, action_matrix)
            print(f"[STATUS]: {execution_result}")
            
            if "SUCCESS" in execution_result:
                print("\n[TERMINAL] Run target execution validated as complete. Shutting down engines.")
                break
                
            session["history"].append({
                "step": step + 1,
                "decision": decision,
                "result": execution_result
            })
            session["loop_count"] = step + 1
            with open(SESSION_FILE, "w") as f:
                json.dump(session, f, indent=4)
                
            time.sleep(1)
            
        browser.close()

if __name__ == "__main__":
    # Interactive Flow Demonstration Target
    run_agent_workflow(
        url="https://www.iwmf.org/",
        goal="Locate the mailing list entry signup section field box, input my email address from the vault, and sign me up. If you need a password or other profile credential data not in the vault, ask me directly."
    )