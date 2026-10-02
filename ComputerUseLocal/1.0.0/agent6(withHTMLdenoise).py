import os
import json
import html
from playwright.sync_api import sync_playwright
from ollama import chat

# Memory Tracking and Architecture Configurations
MEMORY_DIR = "memory"
HISTORY_FILE = os.path.join(MEMORY_DIR, "session_history.txt")
MODEL_NAME = "gemma4:e2b"

# Single source of truth for which accessibility roles the agent can act on
ACTIONABLE_ROLES = [
    "button", "link", "searchbox", "combobox",
    "checkbox", "textbox", "listboxoption", "menuitem"
]


def ask_model(prompt, fallback=""):
    """Single choke-point for every LLM sub-agent call, with unified error handling."""
    try:
        response = chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
        return response.message.content.strip()
    except Exception as e:
        print(f"[MODEL WARNING] Sub-agent call failed: {str(e)}")
        return fallback


def get_ax_value(field):
    """AX tree fields are sometimes {'value': x} dicts and sometimes plain strings."""
    if isinstance(field, dict):
        return field.get("value") or ""
    return field or ""


def get_ax_properties(node):
    """Flatten the AX 'properties' list into a simple {name: value} dict."""
    props = {}
    for prop in node.get("properties", []) or []:
        prop_name = prop.get("name")
        prop_value = get_ax_value(prop.get("value"))
        if prop_name:
            props[prop_name] = prop_value
    return props


def init_system_memory(start_url, global_goal):
    """Resets storage files and builds the baseline history tracker."""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        f.write(f"START_URL: {start_url}\n")
        f.write(f"GLOBAL_GOAL: {global_goal}\n")
        f.write("--- ACTION LOG ---\n")


def extract_raw_page_data(page):
    """Gathers an expanded view of both visible text and deep form/input states.
    
    Pierces form elements to ensure text vectors inside inputs, textareas, and
    comboboxes are extracted cleanly alongside the standard body layout text.
    """
    try:
        # Script extracts basic text alongside custom input value mappings
        extraction_js = """
        () => {
            let data = {
                url: window.location.href,
                title: document.title,
                bodyText: document.body.innerText,
                inputs: []
            };
            document.querySelectorAll('input, textarea, [role="combobox"], [role="textbox"]').forEach(el => {
                data.inputs.push({
                    tagName: el.tagName,
                    id: el.id || '',
                    placeholder: el.getAttribute('placeholder') || '',
                    value: el.value || '',
                    ariaLabel: el.getAttribute('aria-label') || '',
                    name: el.getAttribute('name') || ''
                });
            });
            return data;
        }
        """
        raw_data = page.evaluate(extraction_js)
        return raw_data
    except Exception as e:
        print(f"[ENGINE WARNING] Failed to extract raw page data: {str(e)}")
        return {"url": "unknown", "title": "unknown", "bodyText": "Extraction failed.", "inputs": []}


def clean_and_organize_layout(raw_data):
    """Sub-agent dedicated to turning raw DOM structures into cleanly organized plain text.
    
    It deletes useless web-scraping noise, structures form states, and presents 
    a hyper-readable layout representation optimized purely for automation routing.
    """
    
    print(raw_data.get('bodyText', '')[:2000])
    
    inputs_summary = ""
    for inp in raw_data.get("inputs", []):
        label = inp['ariaLabel'] or inp['placeholder'] or inp['name'] or inp['id']
        if label:
            inputs_summary += f"- State Element -> [{inp['tagName']}] Label/Attr: '{label}' | Current Value Filled: '{inp['value']}'\n"
            
    prompt = f"""
    You are a professional layout cleaning sub-agent. Your job is to format raw web information into perfectly clean, organized plain text for browser automation.
    
    CURRENT SITE URL: {raw_data.get('url')}
    PAGE WINDOW TITLE: {raw_data.get('title')}
    
    LIVE FORM FIELD/INPUT STATES:
    {inputs_summary if inputs_summary else "No interactive input elements detected."}
    
    RAW UNSTRUCTURED BODY TEXT:
    {raw_data.get('bodyText', '')[:4000]}
    
    CRITICAL CONSTRAINTS & HIERARCHY:
    1. PRIORTIZE NAVIGATION FIRST: At the absolute top of your output, list all primary navigation structures, header menus, and links. It is critical that buttons and controls used to jump sections (e.g., 'Log In', 'Sign Up', 'Home', 'Popular', 'Sort', 'Filter') are explicitly surfaced and cleanly grouped together.
    2. STRUCTURE FORM FIELDS: Right below the main navigation block, clearly list all interactive form fields, search bars, and textboxes alongside their placeholder text and active values.
    3. GROUP CONTENT FEEDS: Organize the remaining unstructured body text logically into thematic sections (e.g., main feed posts, sidebar links, informational footers). 
    4. DE-NOISE COMPLETELY: Strip out all code wrappers, timestamp strings, repetitive tracking metadata, layout boilerplate, and unreadable character artifacts.
    5. OUTPUT FORMAT: Provide purely clean, structural, organized plain prose text. Do not return any HTML tags, markdown syntax lists, or JSON blocks.
    """
    
    print("[TERMINAL] Calling Sub-Agent: Layout Cleaner...")
    return ask_model(prompt, fallback="Failed to clean layout safely.")


def generate_context_summary(cleaned_text, global_goal, history, current_url):
    """Sub-agent dedicated to neutrally collapsing page state into relevant context."""
    
    prompt = f"""
    You are a neutral page-state analyzer.

    GLOBAL GOAL: '{global_goal}'
    CURRENT URL: {current_url}
    RECENT HISTORY: {history[-500:]}

    CLEANED PAGE LAYOUT TEXT:
    {cleaned_text}

    Summarize what is on the screen in 2-3 sentences. Filter for ALL information relevant to the goal.
    Leaving out useful information on the screen is worse than having too long a summary.
    Note any visible form fields, whether they appear empty or already filled, any error/validation
    messages, and whether a modal, dropdown, or popup is currently open.
    Rules: State facts only. No next steps. No goal references. No recommendations.
    """
    print("[TERMINAL] Calling Sub-Agent: Summarizer...")
    return ask_model(prompt, fallback="Context summary unavailable.")


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
    return "YES" in ask_model(prompt, fallback="NO").upper()


def generate_next_step_plan(global_goal, page_summary, history, current_url):
    """Planner sub-agent that predicts exactly ONE step into the future."""
    prompt = f"""
    You are the logic planner. 
    GLOBAL GOAL: '{global_goal}'
    CURRENT URL: {current_url}
    CURRENT PAGE SUMMARY: {page_summary}
    HISTORY: {history[-800:]}
    
    CRITICAL CONSTRAINTS:
    1. If you see a cookie banner, modal, or popup, clearing it is your next step.
    2. DROPDOWNS ARE TWO STEPS: If the goal requires sorting (e.g., 'Ending soonest'), click the 'Sort' dropdown first. If the summary indicates a dropdown/menu is OPEN, plan to click the specific option inside it.
    3. VERIFY EXECUTION: Read the 'Result:' of the last action. If a previous action failed or hit a text mismatch, adjust your plan immediately.
    4. TYPING DOES NOT SUBMIT: Filling a field NEVER submits the form. Once ALL required fields are filled, your next step MUST be to click the explicit 'Log In', 'Submit', or 'Search' button.
    5. AVOID DEAD LOOPS: If the history shows the previous step resulted in "No matches," pivot to the next logical step to advance the goal.
    6. THE ESCAPE PROTOCOL: If you are searching for a feed but find yourself trapped inside an isolated single item post or ad, DO NOT SCROLL. Plan to click the main logo or a 'Home' button to escape.
    7. INCORRECT SIGN IN: do NOT sign in using google.
    
    What is the single, immediate next step required? State ONLY ONE action into the future in plain text.
    """
    print("[TERMINAL] Calling Sub-Agent: Planner...")
    return ask_model(prompt, fallback="Scroll down to reveal more options.")


def filter_element_roles(plan):
    """Filter sub-agent to select HTML roles relevant to the planner's decision."""
    prompt = f"""
    PLAN: '{plan}'
    
    Which HTML roles are needed to execute this plan? Choose strictly from this list:
    button, link, searchbox, combobox, checkbox, textbox, listboxoption, menuitem
    
    Respond ONLY with a comma-separated list of the relevant roles. If the plan is to scroll or search the page text, output 'all'.
    """
    print("[TERMINAL] Calling Sub-Agent: Role Filter...")
    response = ask_model(prompt, fallback="all").lower()
    if "all" in response:
        return ACTIONABLE_ROLES
    roles = [r.strip() for r in response.split(",") if r.strip() in ACTIONABLE_ROLES]

    if "click" in plan.lower():
        for essential in ("button", "link"):
            if essential not in roles:
                roles.append(essential)

    return roles if roles else ACTIONABLE_ROLES


def describe_matrix_item(item):
    """Render a single action element with all the extra context we collect."""
    parts = [f"[{item['original_index']}] TYPE: {item['role'].upper()} | LABEL: '{item['name']}'"]

    if item.get("value"):
        parts.append(f"CURRENT_VALUE: '{item['value']}'")
    if item.get("description"):
        parts.append(f"DESC: '{item['description']}'")

    states = []
    for state_key in ("required", "disabled", "checked", "expanded", "focused", "invalid"):
        val = item.get(state_key)
        if val not in (None, "", False, "false", "False"):
            states.append(f"{state_key}={val}")
    if states:
        parts.append("STATE: " + ", ".join(states))

    return " | ".join(parts)


def format_action_json(plan, filtered_matrix):
    """Formatter sub-agent to rigidly output JSON without thinking about the larger goal."""
    flat_matrix = "\n".join(describe_matrix_item(item) for item in filtered_matrix)
    prompt = f"""
    You are a strict JSON formatter. 
    
    YOUR PLAN: '{plan}'
    
    AVAILABLE ELEMENTS:
    {flat_matrix}
    
    Respond ONLY with a raw JSON block matching this exact format:
    {{
        "reasoning": "Briefly state why this index/action matches the plan.",
        "action": "click|type|hover|scroll_down|search",
        "target_index": 0 (set to null if scrolling or searching),
        "type_value": "text to type or search (or null)"
    }}
    """
    print("[TERMINAL] Calling Sub-Agent: JSON Formatter...")
    raw_output = ask_model(prompt, fallback="")

    if "{" not in raw_output or "}" not in raw_output:
        print("[FORMATTER ERROR] No JSON object found in model response.")
        return None

    raw_output = raw_output[raw_output.find("{"):raw_output.rfind("}") + 1]
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError as e:
        print(f"[FORMATTER ERROR] Syntax parsing failed: {str(e)}")
        return None


def build_reconstructed_tree(page):
    """Pulls the accessibility tree via CDP and returns a deduplicated list of actionable nodes."""
    cdp_session = page.context.new_cdp_session(page)
    try:
        tree = cdp_session.send("Accessibility.getFullAXTree")
        all_raw_nodes = tree.get("nodes", [])
    except Exception as e:
        print(f"[ENGINE WARNING] Failed to fetch accessibility tree: {str(e)}")
        return []

    node_directory = {node["nodeId"]: node for node in all_raw_nodes}
    deduplicated_actions = []
    seen_signatures = set()

    for node in all_raw_nodes:
        role = get_ax_value(node.get("role"))
        name = get_ax_value(node.get("name")).strip()
        node_id = node.get("nodeId")
        backend_id = node.get("backendDOMNodeId")

        if role in ["combobox", "searchbox", "textbox"] and not name:
            for child_id in node.get("childIds", []):
                child = node_directory.get(child_id)
                if not child:
                    continue
                name = get_ax_value(child.get("name")).strip() or get_ax_value(child.get("value")).strip()
                if name:
                    break

        if role in ACTIONABLE_ROLES and name and node_id:
            sig = f"{role}||{name}"
            if sig not in seen_signatures:
                value = get_ax_value(node.get("value")).strip()
                description = get_ax_value(node.get("description")).strip()
                props = get_ax_properties(node)

                deduplicated_actions.append({
                    "cdp_id": node_id,
                    "backend_dom_id": backend_id,
                    "role": role,
                    "name": name,
                    "value": value,
                    "description": description,
                    "required": props.get("required"),
                    "disabled": props.get("disabled"),
                    "checked": props.get("checked"),
                    "expanded": props.get("expanded"),
                    "focused": props.get("focused"),
                    "invalid": props.get("invalid"),
                })
                seen_signatures.add(sig)

    return deduplicated_actions


def _locate_exact_node(page, backend_dom_id):
    """Tag the EXACT DOM node behind a chosen AX node and return a locator for it."""
    if backend_dom_id is None:
        return None, None

    cdp = page.context.new_cdp_session(page)
    try:
        resolved = cdp.send("DOM.resolveNode", {"backendNodeId": backend_dom_id})
        object_id = resolved["object"]["objectId"]
        cdp.send("Runtime.callFunctionOn", {
            "objectId": object_id,
            "functionDeclaration": "function(){ this.setAttribute('data-agent-target','x'); }",
        })
    except Exception as e:
        print(f"[ENGINE WARNING] Backend node resolution failed: {str(e)}")
        return None, None

    locator = page.locator("[data-agent-target='x']").first

    def cleanup():
        try:
            cdp.send("Runtime.callFunctionOn", {
                "objectId": object_id,
                "functionDeclaration": "function(){ this.removeAttribute('data-agent-target'); }",
            })
        except Exception:
            pass

    return locator, cleanup


def execute_matrix_action(page, decision_block, action_matrix):
    """Resolves the chosen element and dispatches atomic browser events."""
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
        matches = [
            f"Index [{idx}] ({item['role']})"
            for idx, item in enumerate(action_matrix)
            if type_text.lower() in item["name"].lower()
        ]
        if matches:
            return f"SEARCH RESULTS for '{type_text}': Found at {', '.join(matches)}."
        return f"SEARCH RESULTS for '{type_text}': No matches."

    if target_idx is None or target_idx >= len(action_matrix):
        return "Failed: Selected index exists outside active layout grid limits."

    chosen_element = action_matrix[target_idx]
    role = chosen_element["role"]
    name = chosen_element["name"]
    clean_name = html.unescape(name).split("─")[0].strip()
    clean_name = clean_name if len(clean_name) >= 3 else name[:25]

    print(f"[EXECUTING NATIVE TRIGGER]: Target Action: {action_type} | Selected Node: {role.upper()} | Text Vector: '{clean_name}'")

    locator, cleanup = _locate_exact_node(page, chosen_element.get("backend_dom_id"))

    if locator is None or locator.count() == 0:
        resolved_role = role if role != "searchbox" else "textbox"
        locator = page.get_by_role(resolved_role, name=clean_name, exact=True).first
        if locator.count() == 0 or not locator.is_visible():
            locator = page.get_by_role(resolved_role, name=clean_name, exact=False).first
        if locator.count() == 0 or not locator.is_visible():
            locator = page.locator(f"text='{clean_name}'").first
        cleanup = None

    try:
        if action_type == "HOVER":
            locator.hover()
            page.wait_for_timeout(1000)
            return f"Successfully hovered over element: '{clean_name}'"

        elif action_type == "TYPE":
            locator.fill(type_text if type_text else "")
            return (f"Successfully typed '{type_text}' into: '{clean_name}'. "
                    f"Field is filled but NOT submitted; a separate click on button is required.")

        elif action_type == "CLICK":
            locator.evaluate("node => node.removeAttribute('target')")
            locator.click(force=True)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)
            return f"Successfully clicked element: '{clean_name}'"

        else:
            return f"Failed: Unrecognized action type '{action_type}'."

    except Exception as e:
        return f"Execution aborted via runtime driver exception: {str(e)}"
    finally:
        if cleanup:
            cleanup()


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
            if check_goal_completion(goal, current_history_text):
                print("[STATUS]: SUCCESS: Target objective fulfilled. Halting active agent pipeline.")
                break

            try:
                current_url = page.url
            except Exception:
                current_url = "unknown"

            # Phase 2: Structural Data Extraction & Layout De-noising
            raw_page_data = extract_raw_page_data(page)
            cleaned_layout_text = clean_and_organize_layout(raw_page_data)
            
            # Phase 3: Context Extraction & Summary
            page_summary = generate_context_summary(cleaned_layout_text, goal, current_history_text, current_url)
            print(f"[SUMMARY]: {page_summary}")

            # Phase 4: The Planner
            plan = generate_next_step_plan(goal, page_summary, current_history_text, current_url)
            print(f"[PLANNER]: {plan}")

            # Phase 5: Role Filter
            allowed_roles = filter_element_roles(plan)
            print(f"[FILTER]: Proceeding with roles: {allowed_roles}")

            # Matrix Construction & Python Filtering
            action_matrix = build_reconstructed_tree(page)
            for idx, item in enumerate(action_matrix):
                item["original_index"] = idx

            if not action_matrix:
                print("[STATUS]: No actionable elements found this cycle. Scrolling to reveal more.")
                page.mouse.wheel(0, 800)
                page.wait_for_timeout(1000)
                continue

            filtered_matrix = [item for item in action_matrix if item["role"] in allowed_roles]
            if not filtered_matrix:
                filtered_matrix = action_matrix

            # Phase 6: JSON Formatter
            decision = format_action_json(plan, filtered_matrix)
            if not decision:
                continue

            print(f"[FORMATTER]: {decision.get('reasoning', 'No reasoning provided.')}")

            # Phase 7: Execution
            execution_result = execute_matrix_action(page, decision, action_matrix)
            print(f"[STATUS]: {execution_result}")

            if len(page.context.pages) > 1:
                new_active_page = page.context.pages[-1]
                new_active_page.bring_to_front()
                for background_page in page.context.pages[:-1]:
                    try:
                        background_page.close()
                    except Exception:
                        pass
                page = new_active_page

            log_entry = (
                f"Step {step + 1} | Plan: {plan} | Action Taken: {decision.get('action')} | "
                f"Target/Query: {decision.get('type_value') or decision.get('target_index')} | "
                f"Result: {execution_result}\n"
            )
            with open(HISTORY_FILE, "a") as f:
                f.write(log_entry)

        print("\n[TERMINAL] Processing run target finished.")
        browser.close()


if __name__ == "__main__":
    run_agent_workflow(
        url="https://www.reddit.com",
        goal="Login to reddit using my account. Use the email address '<REDDIT_EMAIL>' and the password '<REDDIT_PASSWORD>'"
    )