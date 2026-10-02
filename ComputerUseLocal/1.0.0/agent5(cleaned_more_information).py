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
    """Flatten the AX 'properties' list into a simple {name: value} dict.

    The accessibility node stores state flags (focused, required, disabled,
    checked, expanded, invalid, etc.) inside a 'properties' list of
    {'name': ..., 'value': {'value': ...}} objects. This collapses them into
    a flat lookup so we can surface them to the model.
    """
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


def extract_page_text(page):
    """Grabs visible plain text from the DOM, avoiding heavy CSS computed style loops.

    Now also prepends the live URL and page title so downstream sub-agents have
    explicit location awareness (e.g. knowing they are on a login screen, a
    single post, or the main feed).
    """
    try:
        raw_text = page.evaluate("document.body.innerText")
        text_body = raw_text[:4000] if raw_text else "No readable text found on current screen."
        try:
            current_url = page.url
        except Exception:
            current_url = "unknown"
        try:
            page_title = page.title()
        except Exception:
            page_title = "unknown"
        return (
            f"CURRENT URL: {current_url}\n"
            f"PAGE TITLE: {page_title}\n\n"
            f"VISIBLE TEXT:\n{text_body}"
        )
    except Exception as e:
        print(f"[ENGINE WARNING] Failed to extract page text: {str(e)}")
        return "Text extraction failed."


def generate_context_summary(page_text, global_goal, history, current_url):
    """Sub-agent dedicated to neutrally collapsing page state into relevant context."""
    
    prompt = f"""
    You are a neutral page-state analyzer.

    GLOBAL GOAL: '{global_goal}'
    CURRENT URL: {current_url}
    RECENT HISTORY: {history[-500:]}

    CURRENT PAGE TEXT:
    {page_text}

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
    2. DROPDOWNS ARE TWO STEPS: If the goal requires sorting (e.g., 'Ending soonest' or 'Lowest price'), you must FIRST plan to click the 'Sort' dropdown. On the VERY NEXT step, you must plan to click the specific sort option. If the page summary already indicates a dropdown/menu is OPEN or EXPANDED, do NOT click the dropdown header again; plan to click the specific option inside it.
    3. VERIFY EXECUTION: Always read the 'Result:' of the last action in your HISTORY. If your previous plan was to click a specific option, but the result shows only a dropdown header (like 'Sort') was clicked, you MUST plan to click that specific option again in this step. Do not skip ahead.
    4. TYPING DOES NOT SUBMIT: Filling a field NEVER submits the form. If your last action was typing into a field (and the Result says it was filled but NOT submitted), your next step depends on what remains: if other required fields are still empty (e.g., you typed the username but not the password), plan to type into the next field. Do NOT re-type into a field that the summary or element states already shows a CURRENT_VALUE. Once ALL required fields are filled, your next step MUST be to click the explicit 'Log In', 'Submit', or 'Search' button. Do NOT assume success until you have clicked that button and the resulting page confirms it.
    5. AVOID DEAD LOOPS: If the history shows the previous step resulted in "SEARCH RESULTS... No matches." for a specific button (like 'Log In'), that element no longer exists on the screen. Do not plan to click it again. Pivot to the next logical step to advance the goal.
    6. THE ESCAPE PROTOCOL: If you are searching for a general feed or list of items, but the current summary indicates you are trapped inside a single, specific post/item page (e.g., a single event promotion, a specific discussion thread, an ad), DO NOT SCROLL. Your immediate next step MUST be to plan to click the site's main logo, a 'Home' button, or a 'Back' button to escape the single post and return to the main feed.
    7. INCORRECT SIGN IN: do NOT sign in using google
    
    What is the single, immediate next step required? State ONLY ONE action into the future in plain text (e.g., 'Type Nvidia into the search bar', 'Click the Search button', 'Click the Auctions filter', 'Click the Sort dropdown', 'Click the Ending Soonest option', 'Click the Reddit logo to return home').
    """
    print("[TERMINAL] Calling Sub-Agent: Planner...")
    return ask_model(prompt, fallback="Scroll down to reveal more options.")


def filter_element_roles(plan):
    """Filter sub-agent to select HTML roles relevant to the planner's decision."""
    prompt = f"""
    PLAN: '{plan}'
    
    Which HTML roles are needed to execute this plan? Choose strictly from this list:
    button, link, searchbox, combobox, checkbox, textbox, listboxoption, menuitem
    
    Respond ONLY with a comma-separated list of the relevant roles. If the plan is to scroll or search the page text, or if you are unsure, output 'all'.
    """
    print("[TERMINAL] Calling Sub-Agent: Role Filter...")
    response = ask_model(prompt, fallback="all").lower()
    if "all" in response:
        return ACTIONABLE_ROLES
    roles = [r.strip() for r in response.split(",") if r.strip() in ACTIONABLE_ROLES]

    # Submit/login/search controls are unpredictably either a button OR a link.
    # If the plan is a click, never let the filter drop one of the two.
    if "click" in plan.lower():
        for essential in ("button", "link"):
            if essential not in roles:
                roles.append(essential)

    return roles if roles else ACTIONABLE_ROLES


def describe_matrix_item(item):
    """Render a single action element with all the extra context we now collect.

    Surfaces the element's current value, accessible description, and any state
    flags so the formatter can distinguish, e.g., an empty password field from
    a filled one, or an already-expanded dropdown.
    """
    parts = [f"[{item['original_index']}] TYPE: {item['role'].upper()} | LABEL: '{item['name']}'"]

    if item.get("value"):
        parts.append(f"CURRENT_VALUE: '{item['value']}'")
    if item.get("description"):
        parts.append(f"DESC: '{item['description']}'")

    states = []
    for state_key in ("required", "disabled", "checked", "expanded", "focused", "invalid"):
        val = item.get(state_key)
        # Skip empties and explicit false/negative flags to keep the line readable
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
    
    AVAILABLE ELEMENTS (CURRENT_VALUE shows text already inside a field; STATE shows flags like expanded/checked/disabled/focused):
    {flat_matrix}
    
    CRITICAL CONSTRAINTS:
    1. Choose your action from: "click", "type", "hover", "scroll_down", or "search".
    2. "search" is a find-in-page native tool to scan for plain text. 
    3. "type" is for typing into physical search bars or textboxes. You MUST provide the text in 'type_value'. Do NOT 'type' into a field whose CURRENT_VALUE already holds the intended text.
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
    """Pulls the accessibility tree via CDP and returns a deduplicated list of actionable nodes.

    Each node captures its current value, accessible description, the key state
    flags, and — critically — the backendDOMNodeId so execution can target the
    EXACT element instead of re-resolving by an ambiguous role+name string.
    """
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
        backend_id = node.get("backendDOMNodeId")  # links AX node -> real DOM node

        # For unlabeled inputs, borrow a name from the first labeled child
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
    """Tag the EXACT DOM node behind a chosen AX node and return a locator for it.

    Resolves the backendDOMNodeId to a live JS handle via CDP, stamps a unique
    attribute on it, and locates by that attribute. This eliminates the
    text-collision bug where get_by_role(name='Log In').first matched the header
    link instead of the modal submit button. CSS locators also pierce open shadow
    DOM and frames, so this works inside Reddit's faceplate/iframe login modal.
    Returns (locator, cleanup_fn) or (None, None) on failure.
    """
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
    """Resolves the chosen element and dispatches atomic browser events.

    Clicks/types/hovers the EXACT node selected by index (via backendDOMNodeId),
    not a re-resolved text match, so it can no longer hit the wrong 'Log In'.
    """
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

    # Primary path: target the EXACT node by backend id (no text collisions).
    locator, cleanup = _locate_exact_node(page, chosen_element.get("backend_dom_id"))

    # Fallback path: old text-based resolution if backend resolution failed.
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
                    f"Field is filled but NOT submitted; a separate click on the "
                    f"submit/login/search button is still required.")

        elif action_type == "CLICK":
            locator.evaluate("node => node.removeAttribute('target')")  # prevent new tabs
            # Dropped force=True: a real actionability check prevents clicking an
            # element hidden behind the modal overlay (the header 'Log In' link).
            locator.click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2000)  # let modals/dropdowns settle
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

            # Capture live location once per cycle for location-aware sub-agents
            try:
                current_url = page.url
            except Exception:
                current_url = "unknown"

            # Phase 2: Context Extraction & Summary
            raw_page_text = extract_page_text(page)
            page_summary = generate_context_summary(raw_page_text, goal, current_history_text, current_url)
            print(f"[SUMMARY]: {page_summary}")

            # Phase 3: The Planner
            plan = generate_next_step_plan(goal, page_summary, current_history_text, current_url)
            print(f"[PLANNER]: {plan}")

            # Phase 4: Role Filter
            allowed_roles = filter_element_roles(plan)
            print(f"[FILTER]: Proceeding with roles: {allowed_roles}")

            # Matrix Construction & Python Filtering
            action_matrix = build_reconstructed_tree(page)
            for idx, item in enumerate(action_matrix):
                item["original_index"] = idx  # Preserve absolute index for execution

            if not action_matrix:
                print("[STATUS]: No actionable elements found this cycle. Scrolling to reveal more.")
                page.mouse.wheel(0, 800)
                page.wait_for_timeout(1000)
                continue

            filtered_matrix = [item for item in action_matrix if item["role"] in allowed_roles]
            if not filtered_matrix:
                filtered_matrix = action_matrix  # Safe fallback if filter was too strict

            # Phase 5: JSON Formatter
            decision = format_action_json(plan, filtered_matrix)
            if not decision:
                continue

            print(f"[FORMATTER]: {decision.get('reasoning', 'No reasoning provided.')}")

            # Phase 6: Execution
            execution_result = execute_matrix_action(page, decision, action_matrix)
            print(f"[STATUS]: {execution_result}")

            # Consolidate to the newest tab if a popup/new tab slipped through
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