import os
import asyncio
from playwright.async_api import async_playwright
import openai
import json

# Poe API client setup
client = openai.OpenAI(
    api_key=os.getenv("POE_API_KEY", ""),
    base_url="https://api.poe.com/v1",
)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # set True if you don’t want to see the browser
        page = await browser.new_page()
        await page.goto("https://www.kaggle.com")

        for step in range(3):  # limit number of steps for safety
            html = await page.content()

            # Send HTML to LLM for analysis
            chat = client.chat.completions.create(
                model="GPT-OSS-120B-CS",
                messages=[
                    {
                        "role": "user",
                        "content": f"""
You are controlling a web browser. Here is the current page HTML:

{html[:5000]}   # <-- truncate to avoid sending too much

Click the Models button
Respond ONLY in JSON with this format:
{{
  "action": "click" | "navigate" | "type" | "none",
  "target": "CSS selector or URL",
  "text": "optional text input"
}}
"""
                    }
                ],
            )

            response = chat.choices[0].message.content.strip()
            print("Model response:", response)

            try:
                action = json.loads(response)
            except json.JSONDecodeError:
                print("Invalid response, stopping.")
                break

            # Execute the action
            if action["action"] == "click":
                await page.click(action["target"])
            elif action["action"] == "navigate":
                await page.goto(action["target"])
            elif action["action"] == "type":
                await page.fill(action["target"], action["text"])
            elif action["action"] == "none":
                print("No action suggested. Stopping.")
                break

        await browser.close()

asyncio.run(main())
