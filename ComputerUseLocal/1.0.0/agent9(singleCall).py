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

# Roles whose NAME meaningfully describes a container/landmark we want as context
CONTEXT_ROLES = (
    "dialog", "alertdialog", "form", "navigation", "search",
    "banner", "main", "region", "menu", "list", "complementary", "contentinfo"
)

# How interactive elements are bucketed when presented to the model
INVENTORY_BUCKETS = [
    ("TEXT INPUTS / SEARCH FIELDS  (you can TYPE here)", ("textbox", "searchbox", "combobox")),
    ("BUTTONS  (CLICK to submit / trigger an action)", ("button",)),
    ("LINKS  (CLICK to navigate)", ("link",)),
    ("CHECKBOXES / MENU OPTIONS  (CLICK to select)", ("checkbox", "menuitem", "listboxoption")),
]


class PageStateTracker:
    SURVIVAL_THRESHOLD = 0.2

    def __init__(self):
        self.prev_lines = set()
        self.prev_url = None
        self.baseline_sigs = set()   
        self.overlay_sigs = set()    
        self.first = True

    def analyze(self, current_lines, current_url, current_sigs):
        current_sigs = set(current_sigs)
        current_lines = list(current_lines)
        was_first = self.first

        if was_first:
            diff_lines = list(current_lines)
        else:
            diff_lines = [line for line in current_lines if line not in self.prev_lines]

        if was_first:
            new_sigs = set()
            self.baseline_sigs = current_sigs
            self.overlay_sigs = set()
        else:
            navigated = current_url != self.prev_url
            survival = (
                len(self.baseline_sigs & current_sigs) / len(self.baseline_sigs)
                if self.baseline_sigs else 0.0
            )

            if navigated or survival < self.SURVIVAL_THRESHOLD:
                new_sigs = set()
                self.baseline_sigs = current_sigs
                self.overlay_sigs = set()
            else:
                known = self.baseline_sigs | self.overlay_sigs
                appeared = current_sigs - known
                self.overlay_sigs = (self.overlay_sigs & current_sigs) | appeared
                new_sigs = set(self.overlay_sigs)

        self.prev_lines = set(current_lines)
        self.prev_url = current_url
        self.first = False
        return was_first, diff_lines, new_sigs


def ask_model(prompt, fallback=""):
    try:
        response = chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
        return response.message.content.strip()
    except Exception as e:
        print(f"[MODEL WARNING] Sub-agent call failed: {str(e)}")
        return fallback


def get_ax_value(field):
    if isinstance(field, dict):
        return field.get("value") or ""
    return field or ""


def get_ax_properties(node):
    props = {}
    for prop in node.get("properties", []) or []:
        prop_name = prop.get("name")
        prop_value = get_ax_value(prop.get("value"))
        if prop_name:
            props[prop_name] = prop_value
    return props


def init_system_memory(start_url, global_goal):
    os.makedirs(MEMORY_DIR, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        f.write(f"START_URL: {start_url}\n")
        f.write(f"GLOBAL_GOAL: {global_goal}\n")
        f.write("--- ACTION LOG ---\n")


def extract_raw_page_data(page):
    try:
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


def normalize_body_lines(body_text):
    return [line.strip() for line in (body_text or "").splitlines() if line.strip()]


def clean_and_organize_layout(raw_data, diff_lines, inventory_text, is_first):
    if is_first:
        body_block_header = "FULL PAGE BODY TEXT (first page load):"
    elif diff_lines:
        body_block_header = ("NEWLY APPEARED CONTENT ONLY (the difference vs. the previous page — "
                             "e.g. a form, modal, or dropdown that just opened):")
    else:
        body_block_header = ("NEWLY APPEARED CONTENT: (none — the page text is essentially unchanged "
                             "from the previous step; rely on the interactive inventory below.)")

    body_block = "\n".join(diff_lines)[:4000] if diff_lines else "(no new text appeared)"

    prompt = f"""
    You are a professional layout cleaning sub-agent. Your job is to format raw web information into perfectly clean, organized plain text for browser automation.

    CURRENT SITE URL: {raw_data.get('url')}
    PAGE WINDOW TITLE: {raw_data.get('title')}

    INTERACTIVE ELEMENT INVENTORY (the exact buttons, fields, links, and options on screen — treat this as the ground truth for what is clickable/typeable):
    {inventory_text}

    {body_block_header}
    {body_block}

    CRITICAL CONSTRAINTS & HIERARCHY:
    1. PRIORITIZE NEW & ACTIONABLE: If a form, modal, or dropdown just appeared, surface it first and describe every field and button inside it explicitly.
    2. NAVIGATION & CONTROLS: Clearly group primary navigation, header menus, and global controls (e.g. 'Log In', 'Sign Up', 'Home', 'Sort', 'Filter').
    3. STRUCTURE FORM FIELDS: List interactive form fields, search bars, and textboxes alongside their labels and any current values.
    4. GROUP CONTENT FEEDS: Organize remaining body text into logical thematic sections.
    5. DE-NOISE COMPLETELY: Strip code wrappers, timestamps, tracking metadata, boilerplate, and unreadable artifacts.
    6. OUTPUT FORMAT: Provide purely clean, structural, organized plain prose text. No HTML tags, no markdown lists, no JSON.
    """

    print("[TERMINAL] Calling Sub-Agent: Layout Cleaner...")
    return ask_model(prompt, fallback="Failed to clean layout safely.")


def generate_context_summary(cleaned_text, inventory_text, global_goal, history, current_url):
    prompt = f"""
    You are a neutral page-state analyzer.

    GLOBAL GOAL: '{global_goal}'
    CURRENT URL: {current_url}
    RECENT HISTORY: {history[-500:]}

    INTERACTIVE ELEMENTS CURRENTLY ON SCREEN:
    {inventory_text}

    CLEANED PAGE LAYOUT TEXT (changed/new content):
    {cleaned_text}

    Summarize what is on the screen in 2-3 sentences. Filter for ALL information relevant to the goal.
    Leaving out useful information on the screen is worse than having too long a summary.
    Explicitly note any visible form fields (and whether each appears empty or already filled), any
    error/validation messages, and whether a modal, dropdown, or popup is currently open. If new
    interactive elements just appeared, call them out.
    Rules: State facts only. No next steps. No goal references. No recommendations.
    """
    print("[TERMINAL] Calling Sub-Agent: Summarizer...")
    return ask_model(prompt, fallback="Context summary unavailable.")


def check_goal_completion(global_goal, history):
    prompt = f"""
    GLOBAL GOAL: '{global_goal}'

    HISTORY:
    {history}

    Based on the history logs, has the global goal been completely executed?
    Answer strictly with 'YES' or 'NO'. Do not explain.
    """
    print("[TERMINAL] Calling Sub-Agent: Evaluator...")
    return "YES" in ask_model(prompt, fallback="NO").upper()


def generate_next_step_plan(global_goal, page_summary, inventory_text, history, current_url):
    prompt = f"""
    You are the logic planner.
    GLOBAL GOAL: '{global_goal}'
    CURRENT URL: {current_url}
    CURRENT PAGE SUMMARY: {page_summary}

    INTERACTIVE ELEMENTS YOU CAN ACT ON RIGHT NOW (anything marked NEW just appeared this step):
    {inventory_text}

    HISTORY: {history[-800:]}

    CRITICAL CONSTRAINTS:
    1. If you see a cookie banner, modal, or popup, clearing it is your next step.
    2. DROPDOWNS ARE TWO STEPS: If the goal requires sorting (e.g., 'Ending soonest'), click the 'Sort' dropdown first. If the summary indicates a dropdown/menu is OPEN, plan to click the specific option inside it.
    3. VERIFY EXECUTION: Read the 'Result:' of the last action. If a previous action failed or hit a text mismatch, adjust your plan immediately.
    4. TYPING DOES NOT SUBMIT: Filling a field NEVER submits the form. Once ALL required fields are filled, your next step MUST be to click the explicit 'Log In', 'Submit', or 'Search' button.
    5. AVOID DEAD LOOPS: If the history shows the previous step resulted in "No matches," pivot to the next logical step to advance the goal.
    6. THE ESCAPE PROTOCOL: If you are searching for a feed but find yourself trapped inside an isolated single item post or ad, DO NOT SCROLL. Plan to click the main logo or a 'Home' button to escape.
    7. INCORRECT SIGN IN: do NOT sign in using google.
    8. PREFER NEW ELEMENTS: If interactive elements were marked NEW this step (e.g. a login form just opened), your plan should almost always target one of them.

    Reference the exact element LABELS shown in the inventory above when describing your step.
    What is the single, immediate next step required? State ONLY ONE action into the future in plain text.
    """
    print("[TERMINAL] Calling Sub-Agent: Planner...")
    return ask_model(prompt, fallback="Scroll down to reveal more options.")


def filter_element_roles(plan):
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
    parts = [f"[{item['original_index']}] {item['role'].upper()} | LABEL: '{item['name']}'"]
    if item.get("context"):
        parts.append(f"INSIDE: {item['context']}")
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


def format_interactive_inventory(matrix, new_signatures=None):
    if not matrix:
        return "No interactive elements detected on the page."
    new_signatures = new_signatures or set()

    def sig(item):
        return f"{item['role']}||{item['name']}"

    def render_bucketed(items, indent="  "):
        lines = []
        for header, roles in INVENTORY_BUCKETS:
            bucket = [it for it in items if it["role"] in roles]
            if not bucket:
                continue
            lines.append(f"{indent}--- {header} ---")
            for it in bucket:
                lines.append(indent + describe_matrix_item(it))
        return lines

    output = []
    new_items = [it for it in matrix if sig(it) in new_signatures]
    if new_items:
        output.append("⚡⚡ ACTIVE OVERLAY ELEMENTS (part of a popup, modal, form, or section currently layered on top):")
        output.extend(render_bucketed(new_items))
        output.append("")

    output.append("ALL INTERACTIVE ELEMENTS CURRENTLY AVAILABLE:")
    output.extend(render_bucketed(matrix))
    return "\n".join(output)


def format_action_json(plan, filtered_matrix, new_signatures=None):
    new_signatures = new_signatures or set()

    def annotate(item):
        marker = "  <<< NEW" if f"{item['role']}||{item['name']}" in new_signatures else ""
        return describe_matrix_item(item) + marker

    flat_matrix = "\n".join(annotate(item) for item in filtered_matrix)
    prompt = f"""
    You are a strict JSON formatter.

    YOUR PLAN: '{plan}'

    AVAILABLE ELEMENTS (elements marked <<< NEW just appeared this step):
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
        return None

    raw_output = raw_output[raw_output.find("{"):raw_output.rfind("}") + 1]
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        return None


def find_ancestor_context(node, directory):
    current = node
    for _ in range(8):
        parent_id = current.get("parentId")
        if not parent_id:
            break
        parent = directory.get(parent_id)
        if not parent:
            break
        p_role = get_ax_value(parent.get("role"))
        p_name = get_ax_value(parent.get("name")).strip()
        if p_role in CONTEXT_ROLES:
            return f"{p_role} '{p_name}'" if p_name else p_role
        current = parent
    return ""


def build_reconstructed_tree(page):
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
                context = find_ancestor_context(node, node_directory)

                deduplicated_actions.append({
                    "cdp_id": node_id,
                    "backend_dom_id": backend_id,
                    "role": role,
                    "name": name,
                    "value": value,
                    "description": description,
                    "context": context,
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
    except Exception:
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
    action_type = decision_block.get("action", "").upper()
    target_idx = decision_block.get("target_index")
    type_text = decision_block.get("type_value")

    if action_type == "SCROLL_DOWN":
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(1000)
        return "Successfully scrolled down the viewport."

    if action_type == "SEARCH":
        if not type_text:
            return "Failed: SEARCH action requires a text query."
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


# ========================================================
# UNIFIED AGENT ENTRYPOINT CALL
# ========================================================
def agent(goal: str) -> str:
    """Wraps the entire automation system into a single synchronous request block.
    
    Dynamically maps baseline targets based on goal phrases and evaluates the
    entire browser loop until resolution, returning only the final accomplishment sentence.
    """
    # Dynamic Domain Resolver
    if "amazon" in goal.lower():
        url = "https://www.amazon.com"
    elif "reddit" in goal.lower():
        url = "https://www.reddit.com"
    elif "ebay" in goal.lower():
        url = "https://www.ebay.com"
    else:
        url = "https://www.google.com"

    init_system_memory(url, goal)
    tracker = PageStateTracker()

    with sync_playwright() as p:
        print(f"[AGENT INIT] Spawning Chromium targeting {url}...")
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto(url)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)

        max_steps = 20
        page_summary = "Initializing workflow."

        for step in range(max_steps):
            with open(HISTORY_FILE, "r") as f:
                current_history_text = f.read()

            if check_goal_completion(goal, current_history_text):
                print("[STATUS]: Target objective fulfilled. Proceeding to wrap-up summary...")
                break

            try:
                current_url = page.url
            except Exception:
                current_url = "unknown"

            raw_page_data = extract_raw_page_data(page)
            action_matrix = build_reconstructed_tree(page)
            for idx, item in enumerate(action_matrix):
                item["original_index"] = idx

            if not action_matrix:
                page.mouse.wheel(0, 800)
                page.wait_for_timeout(1000)
                continue

            current_lines = normalize_body_lines(raw_page_data.get("bodyText", ""))
            current_sigs = {f"{it['role']}||{it['name']}" for it in action_matrix}

            is_first, diff_lines, new_sigs = tracker.analyze(
                current_lines, current_url, current_sigs
            )

            inventory_text = format_interactive_inventory(action_matrix, new_sigs)
            cleaned_layout_text = clean_and_organize_layout(
                raw_page_data, diff_lines, inventory_text, is_first
            )

            page_summary = generate_context_summary(
                cleaned_layout_text, inventory_text, goal, current_history_text, current_url
            )

            plan = generate_next_step_plan(
                goal, page_summary, inventory_text, current_history_text, current_url
            )

            allowed_roles = filter_element_roles(plan)
            filtered_matrix = [item for item in action_matrix if item["role"] in allowed_roles]
            if not filtered_matrix:
                filtered_matrix = action_matrix

            decision = format_action_json(plan, filtered_matrix, new_sigs)
            if not decision:
                continue

            execution_result = execute_matrix_action(page, decision, action_matrix)

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

        # Extraction and consolidation of absolute final memory files context
        with open(HISTORY_FILE, "r") as f:
            final_history_text = f.read()

        summary_prompt = f"""
        You are a precise, data-grounded execution summarizer. Review the user's original goal, the final page summary, and the sequential session history log.
        Your job is to extract the exact final data point, price, or entity discovered that answers the goal.

        ORIGINAL USER GOAL: {goal}
        FINAL SCREEN STATE SUMMARY: {page_summary}
        SESSION HISTORY LOGS:
        {final_history_text[-2000:]}

        CRITICAL OUTPUT CONSTRAINT:
        Provide ONLY a single sentence stating the final outcome containing the explicit numerical values/prices or names found. Do not summarize the automation steps. Respond directly as an execution accomplishment.
        """
        
        final_message = ask_model(summary_prompt, fallback="Objective process execution cycle reached terminal step.")
        browser.close()
        
        return f"[FINAL ACCOMPLISHMENT]: {final_message}"


if __name__ == "__main__":
    # Example block showing an exclusive blocking code implementation
    result = agent("Search strictly for '27-inch 4K monitor' on amazon. Identify the price of a prominent listing (such as the Dell or LXZ monitor), and confirm that value explicitly.")
    print("\n" + result)