"""
EasyOCR test: 2x upscale + dual-pass (normal/inverted) + line grouping.
Groups adjacent same-line tokens into phrases so multi-word labels
like "Log In" are detected as one clickable region.
Run with:  python ocr_test.py
"""

import io
import numpy as np
from PIL import Image, ImageOps
import easyocr
from playwright.sync_api import sync_playwright

reader = easyocr.Reader(["en"], gpu=True)

SCALE = 2


def ocr_pass(pil_img, label, scale):
    """Run EasyOCR; return tokens with full bbox extents in viewport pixels."""
    results = reader.readtext(np.array(pil_img), detail=1,
                              text_threshold=0.5, low_text=0.3)
    out = []
    for bbox, text, conf in results:
        text = text.strip()
        if not text:
            continue
        xs = [pt[0] / scale for pt in bbox]
        ys = [pt[1] / scale for pt in bbox]
        out.append({
            "text": text,
            "x0": min(xs), "x1": max(xs),
            "y0": min(ys), "y1": max(ys),
            "cy": (min(ys) + max(ys)) / 2,
            "conf": conf,
            "src": label,
        })
    return out


def token_dedup(items, dist=20):
    """Drop duplicate tokens (same text, near-same center) across passes."""
    merged = []
    for it in items:
        cx = (it["x0"] + it["x1"]) / 2
        dup = False
        for m in merged:
            mx = (m["x0"] + m["x1"]) / 2
            if it["text"].lower() == m["text"].lower() and \
               abs(cx - mx) <= dist and abs(it["cy"] - m["cy"]) <= dist:
                if it["conf"] > m["conf"]:
                    m.update(it)
                dup = True
                break
        if not dup:
            merged.append(it)
    return merged


def group_lines(tokens, y_tol=10, gap_factor=1.2):
    """
    Group tokens into phrases:
      1. Cluster by similar vertical center (same line).
      2. Within a line, sort by x and join tokens whose horizontal gap is
         smaller than ~1.2x the average character/space width.
    Returns phrase dicts with a clickable center.
    """
    tokens = sorted(tokens, key=lambda t: t["cy"])

    # --- step 1: bucket into lines by y ---
    lines = []
    for t in tokens:
        placed = False
        for line in lines:
            if abs(t["cy"] - line["cy"]) <= y_tol:
                line["tokens"].append(t)
                # running average of line center
                n = len(line["tokens"])
                line["cy"] = sum(x["cy"] for x in line["tokens"]) / n
                placed = True
                break
        if not placed:
            lines.append({"cy": t["cy"], "tokens": [t]})

    # --- step 2: within each line, merge adjacent tokens into phrases ---
    phrases = []
    for line in lines:
        toks = sorted(line["tokens"], key=lambda t: t["x0"])
        cur = [toks[0]]
        for prev, t in zip(toks, toks[1:]):
            gap = t["x0"] - prev["x1"]
            # typical char height ~ token height; allow a space-sized gap
            char_h = prev["y1"] - prev["y0"]
            if gap <= char_h * gap_factor:
                cur.append(t)
            else:
                phrases.append(cur)
                cur = [t]
        phrases.append(cur)

    # --- build output ---
    out = []
    for group in phrases:
        text = " ".join(t["text"] for t in group)
        x0 = min(t["x0"] for t in group)
        x1 = max(t["x1"] for t in group)
        y0 = min(t["y0"] for t in group)
        y1 = max(t["y1"] for t in group)
        out.append({
            "text": text,
            "x": int((x0 + x1) / 2),
            "y": int((y0 + y1) / 2),
            "conf": min(t["conf"] for t in group),
            "src": ",".join(sorted({t["src"] for t in group})),
        })
    return out


def run_ocr_test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        print("Opening Reddit...")
        page.goto("https://www.reddit.com")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(3000)

        print(f"URL  : {page.url}")
        print(f"Title: {page.title()}\n")

        screenshot_bytes = page.screenshot(type="png", full_page=False)
        with open("reddit_screenshot.png", "wb") as f:
            f.write(screenshot_bytes)

        image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
        W, H = image.size
        print(f"Screenshot size: {W}x{H}  (upscaling {SCALE}x for OCR)\n")

        big = image.resize((W * SCALE, H * SCALE), Image.LANCZOS)
        grey = big.convert("L")
        inverted = ImageOps.invert(grey)
        grey.save("debug_grey.png")
        inverted.save("debug_inverted.png")

        print("Running passes...")
        tokens = ocr_pass(grey, "normal", SCALE) + \
                 ocr_pass(inverted, "inverted", SCALE)
        tokens = token_dedup(tokens)
        phrases = group_lines(tokens)
        phrases.sort(key=lambda it: (it["y"], it["x"]))

        print(f"\n{'='*64}")
        print(f"{'PHRASE':<34}{'CENTER':<14}{'CONF':<7}{'SRC'}")
        print(f"{'='*64}")
        for it in phrases:
            center = f"({it['x']},{it['y']})"
            print(f"{it['text'][:32]:<34}{center:<14}{it['conf']:<7.2f}{it['src']}")

        print(f"\nTokens after dedup: {len(tokens)} | "
              f"Phrases after grouping: {len(phrases)}\n")

        target = next((it for it in phrases
                       if "log in" in it["text"].lower()), None)
        if target:
            print(f"'Log In' found at ({target['x']}, {target['y']}) "
                  f"via {target['src']}. page.mouse.click(x, y) hits it.")
        else:
            print("'Log In' not grouped — try raising gap_factor "
                  "(e.g. 1.5) if the words sit far apart.")

        input("\nPress Enter to close the browser...")
        browser.close()


if __name__ == "__main__":
    run_ocr_test()