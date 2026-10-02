import os
import json
from ollama import chat
from playwright.sync_api import sync_playwright
import browser_agent

# System Memory Configuration
MEMORY_DIR = "memory"
HISTORY_FILE = os.path.join(MEMORY_DIR, "session_history.txt")
SUPERVISOR_NOTES_FILE = os.path.join(MEMORY_DIR, "supervisor_notes.txt")
CHECKLIST_FILE = os.path.join(MEMORY_DIR, "mission_checklist.txt")
MODEL_NAME = "gemma4:e2b"


def ask_supervisor(prompt, fallback=""):
    try:
        response = chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
        return response.message.content.strip()
    except Exception as e:
        print(f"[SUPERVISOR WARNING] Macro-Supervisor call failed: {str(e)}")
        return fallback


def parse_json_safely(raw_output):
    if "{" not in raw_output or "}" not in raw_output:
        return None
    raw_output = raw_output[raw_output.find("{"):raw_output.rfind("}") + 1]
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        return None


def initialize_macro_plan(user_prompt):
    os.makedirs(MEMORY_DIR, exist_ok=True)
    
    prompt = f"""
    You are the high-level Macro-Supervisor Agent. Split this complex query into distinct sequential milestones.
    GLOBAL MACRO GOAL: "{user_prompt}"
    
    Respond ONLY with a raw JSON block matching this exact schema:
    {{
        "analysis": "Brief high-level strategic plan observation.",
        "checklist": [
            "First standalone subtask step text",
            "Second subtask step text"
        ],
        "suggested_start_url": "Full absolute initial target starting website link"
    }}
    """
    print("[ORCHESTRATOR] Consulting Macro-Supervisor for Initial Planning...")
    raw_response = ask_supervisor(prompt)
    data = parse_json_safely(raw_response)
    
    if not data:
        data = {
            "analysis": "Executing default unified path layout.",
            "checklist": [user_prompt],
            "suggested_start_url": "https://www.amazon.com"
        }
        
    with open(SUPERVISOR_NOTES_FILE, "w") as f:
        f.write(f"STRATEGIC ANALYSIS:\n{data['analysis']}\n")
        
    with open(CHECKLIST_FILE, "w") as f:
        for item in data['checklist']:
            f.write(f"[ ] {item}\n")
            
    return data['checklist'], data['suggested_start_url']


def run_macro_orchestrator(global_goal):
    print("========================================================")
    print("⚡⚡ STARTING PERSISTENT MULTI-AGENT ORCHESTRATION ⚡⚡")
    print("========================================================")
    
    checklist, start_url = initialize_macro_plan(global_goal)
    
    # Initialize the single, persistent Playwright Context at the Orchestrator level
    with sync_playwright() as p:
        print(f"\n[AGENT INIT] Spawning continuous browser context for: {start_url}")
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Initialize global text context tracking files
        browser_agent.init_system_memory(start_url, global_goal)
        
        # Navigate once to the initial master domain targets
        page.goto(start_url)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)
        
        # Sequential multi-step delegation pipeline
        for index, subtask in enumerate(checklist):
            print(f"\n======================== ORCHESTRATOR PHASE {index + 1} ========================")
            print(f"--- ROUTING LIVE WORKER SESSION TO SUBTASK: '{subtask}' ---")
            
            # Pass the single live active `page` context window straight into the worker
            worker_outcome = browser_agent.agent(goal=subtask, page=page)
            
            print(f"\n[WORKER STATUS]: Finished Subtask {index + 1}")
            print(worker_outcome)
            
            with open(SUPERVISOR_NOTES_FILE, "a") as f:
                f.write(f"- Step {index + 1} Completed: {subtask} -> Result: {worker_outcome}\n")
                
        print("\n========================================================")
        print("[STATUS]: Task sequence finished. Formulating terminal assessment...")
        print("========================================================")
        
        try:
            with open(HISTORY_FILE, "r") as f:
                final_history = f.read()[-2000:]
        except Exception:
            final_history = "No log files found."
            
        summary_prompt = f"""
        You are the Master Orchestrator Summary Agent. Formulate the final macro-accomplishment message.
        GLOBAL MACRO GOAL: "{global_goal}"
        HISTORY SUMMARY METRICS:
        {final_history}
        """
        macro_accomplishment = ask_supervisor(summary_prompt, fallback="Macro execution successfully concluded.")
        
        # Clean down structural logging files, but preserve browser instance loop space
        print("\n[CLEANUP]: Flushing temporary memory registers...")
        for tracking_file in [HISTORY_FILE, SUPERVISOR_NOTES_FILE, CHECKLIST_FILE]:
            if os.path.exists(tracking_file):
                os.remove(tracking_file)
        if os.path.exists(MEMORY_DIR) and not os.listdir(MEMORY_DIR):
            os.rmdir(MEMORY_DIR)
            
        print("[CLEANUP DONE]: Cognitive states flushed.")
        print("\n--- 🏁 Final Macro Execution Results 🏁 ---")
        print(macro_accomplishment)
        
        # BROWSER HOLD LOCK: Keeps the execution process alive until you manually exit out of your terminal
        print("\n========================================================")
        input("👉 [LIVE VIEW ACTIVE] Press Enter in this terminal window to close the browser and exit program...")
        print("Closing active browser stream context. Goodbye.")


if __name__ == "__main__":
    complex_objective = (
        "Go to Amazon and work only on Amazon pages. "
        "Search exactly for '27-inch 4K monitor'. "
        "From the search results, identify 3 prominent non-sponsored listings from recognizable brands if possible. "
        "For each candidate, open the product page and verify all of the following from the page itself: "
        "current price, screen size, resolution, refresh rate, seller/shipping availability, and whether the item appears in stock. "
        "Reject any listing that is sponsored, unavailable, not actually 27-inch, or not actually 4K. "
        "Then choose the single best valid listing using this priority order: "
        "lowest current price first, then strongest brand recognition, then best refresh rate. "
        "After choosing, return to that product page and confirm the final selected item title and exact displayed price. "
        "Your final answer must clearly include: "
        "(1) the search phrase used, "
        "(2) the 3 evaluated listings with their prices, "
        "(3) the reason any listing was rejected, "
        "(4) the winning product title, and "
        "(5) the exact final confirmed price copied from the product page. "
        "Do not guess, and do not report a price unless you explicitly saw it on the Amazon page."
    )
    run_macro_orchestrator(complex_objective)