import time
from playwright.sync_api import sync_playwright

ACTIONABLE_ROLES = [
    "button", "link", "searchbox", "combobox",
    "checkbox", "textbox", "menuitem",
    # --- autocomplete / dropdown results ---
    "option",            # <-- the one that was killing you
    "listbox",           # the container (optional; useful as a signal)
    "menuitemradio",
    "menuitemcheckbox",
    "treeitem",
    "tab",
    "radio",
    "switch",
]

TEST_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
<style>
  body { font-family: sans-serif; padding: 40px; }
  .wrap { position: relative; width: 320px; }
  input { width: 100%; padding: 10px; font-size: 16px; box-sizing: border-box; }
  .dropdown {
    position: absolute; top: 42px; left: 0; right: 0;
    border: 1px solid #ccc; background: #fff; display: none; z-index: 10;
  }
  .dropdown div { padding: 10px; cursor: pointer; }
  .dropdown div:hover { background: #eef; }
  #chosen { margin-top: 20px; font-weight: bold; color: green; }
</style>
</head>
<body>
  <h3>Origin city</h3>
  <div class="wrap">
    <input id="city" type="text" placeholder="City or airport"
           role="searchbox" aria-label="From City or airport" autocomplete="off">
    <div class="dropdown" id="dd" role="listbox" aria-label="City suggestions"></div>
  </div>
  <div id="chosen"></div>

<script>
  const DATA = [
    "Charlotte (CLT)", "Charleston (CHS)", "Chattanooga (CHA)",
    "Chicago (ORD)", "Dallas (DFW)", "Los Angeles (LAX)"
  ];
  const input = document.getElementById('city');
  const dd = document.getElementById('dd');
  const chosen = document.getElementById('chosen');

  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    dd.innerHTML = '';
    if (!q) { dd.style.display = 'none'; return; }
    const matches = DATA.filter(d => d.toLowerCase().includes(q));
    if (matches.length === 0) { dd.style.display = 'none'; return; }
    matches.forEach(m => {
      const opt = document.createElement('div');
      opt.textContent = m;
      opt.setAttribute('role', 'option');
      opt.setAttribute('tabindex', '0');
      opt.addEventListener('click', () => {
        chosen.textContent = 'Selected: ' + m;
        input.value = m;
        dd.style.display = 'none';
      });
      dd.appendChild(opt);
    });
    dd.style.display = 'block';
  });
</script>
</body>
</html>
"""


def get_ax_value(field):
    if isinstance(field, dict):
        return field.get("value") or ""
    return field or ""


def build_full_named_tree(page):
    """
    DIAGNOSTIC version: returns EVERY node that has an accessible name,
    regardless of role, plus an 'ignored' flag telling us whether the
    role would have survived the ACTIONABLE_ROLES filter. This lets us
    see what role the dropdown options are actually getting.
    """
    cdp_session = page.context.new_cdp_session(page)
    try:
        tree = cdp_session.send("Accessibility.getFullAXTree")
        all_raw_nodes = tree.get("nodes", [])
    except Exception as e:
        print(f"[ENGINE WARNING] Failed to fetch accessibility tree: {str(e)}")
        return []

    results = []
    for node in all_raw_nodes:
        role = get_ax_value(node.get("role"))
        name = get_ax_value(node.get("name")).strip()
        ignored = node.get("ignored", False)
        if name:  # keep anything with a label, no role filtering yet
            results.append({
                "role": role,
                "name": name,
                "ignored": ignored,
                "would_pass_filter": role in ACTIONABLE_ROLES,
            })
    return results


def snapshot_signatures(matrix):
    return {f"{item['role']}||{item['name']}" for item in matrix}


def describe_diff(before_sigs, after_sigs):
    appeared = sorted(after_sigs - before_sigs)
    disappeared = sorted(before_sigs - after_sigs)
    if not appeared and not disappeared:
        return None
    lines = []
    if appeared:
        lines.append("NEW NAMED ELEMENTS APPEARED:")
        for sig in appeared:
            role, name = sig.split("||", 1)
            passes = "PASSES filter" if role in ACTIONABLE_ROLES else ">>> FILTERED OUT <<<"
            lines.append(f"  + role='{role}' name='{name}'   [{passes}]")
    if disappeared:
        lines.append("ELEMENTS THAT DISAPPEARED:")
        for sig in disappeared:
            role, name = sig.split("||", 1)
            lines.append(f"  - role='{role}' name='{name}'")
    return "\n".join(lines)


def run_diff_test():
    with sync_playwright() as p:
        print("[TEST] Launching browser. Type 'char' into the box to trigger the dropdown.")
        print("[TEST] Watch the terminal for diffs. Ctrl+C to stop.\n")
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_content(TEST_PAGE_HTML)
        page.wait_for_timeout(500)

        last_sigs = snapshot_signatures(build_full_named_tree(page))
        print(f"[TEST] Baseline captured: {len(last_sigs)} named elements.\n")

        try:
            while True:
                page.wait_for_timeout(700)
                current = build_full_named_tree(page)
                current_sigs = snapshot_signatures(current)

                diff_text = describe_diff(last_sigs, current_sigs)
                if diff_text:
                    print("=" * 60)
                    print("[DIFF DETECTED]")
                    print(diff_text)
                    print("=" * 60 + "\n")
                    last_sigs = current_sigs
        except KeyboardInterrupt:
            print("\n[TEST] Stopped by user.")
        finally:
            browser.close()


if __name__ == "__main__":
    run_diff_test()