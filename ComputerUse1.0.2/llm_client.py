import json
import re
import openai
from config import LLM_CONFIG, PROMPTS, SYSTEM_CONFIG

class LLMClient:
    """Handles communication with the Language Model"""

    def __init__(self):
        # Get the selected LLM provider from SYSTEM_CONFIG
        self.provider_name = SYSTEM_CONFIG["llm_provider"]
        if self.provider_name not in LLM_CONFIG:
            raise ValueError(f"Invalid LLM provider specified: {self.provider_name}")

        # Get configuration for the selected provider
        provider_config = LLM_CONFIG[self.provider_name]

        self.client = openai.OpenAI(
            api_key=provider_config["api_key"],
            base_url=provider_config["base_url"],
        )
        self.model = provider_config["model"]
        self.max_tokens = provider_config["max_tokens"]
        self.temperature = provider_config["temperature"]

    def extract_json_from_response(self, content):
        """Extract JSON from LLM response that may contain markdown or other text"""
        # Poe's model returns raw JSON, so we handle that case first
        if self.provider_name == "poe":
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

        # If that fails or if it's a DeepSeek response, look for JSON code blocks
        json_pattern = r'```json\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, content, re.DOTALL | re.IGNORECASE)

        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass

        # Look for any JSON-like structure (starting with { and ending with })
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, content, re.DOTALL)

        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        # If no valid JSON found, raise an error
        raise json.JSONDecodeError(f"No valid JSON found in response: {content[:200]}...")

    async def get_action(self, html, task, context=None, history_context=None):
        """Get the next action from the LLM with history awareness"""
        try:
            prompt = PROMPTS["main_prompt"].format(html=html, task=task)

            messages = [
                {"role": "system", "content": PROMPTS["system_prompt"]},
                {"role": "user", "content": prompt}
            ]

            # Add context if provided
            if context:
                messages.append({"role": "user", "content": context})

            # Add history context if provided
            if history_context:
                history_msg = f"Action history context:\n{history_context}"
                messages.append({"role": "user", "content": history_msg})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            content = response.choices[0].message.content.strip()
            print(f"LLM Response: {content}")

            # Extract JSON from response
            try:
                action_data = self.extract_json_from_response(content)
                return {"success": True, "action": action_data}
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                return {"success": False, "error": f"Invalid JSON response: {content[:500]}..."}

        except Exception as e:
            print(f"LLM request failed: {e}")
            return {"success": False, "error": str(e)}

    async def handle_error(self, html, error_message, task, history_context=None):
        """Get a recovery action when an error occurs"""
        try:
            prompt = PROMPTS["error_prompt"].format(html=html, error=error_message)

            messages = [
                {"role": "system", "content": PROMPTS["system_prompt"]},
                {"role": "user", "content": f"Original task: {task}"},
                {"role": "user", "content": prompt}
            ]

            # Add history context for better error recovery
            if history_context:
                history_msg = f"Previous actions that led to this error:\n{history_context}"
                messages.append({"role": "user", "content": history_msg})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            content = response.choices[0].message.content.strip()
            print(f"LLM Error Recovery Response: {content}")

            try:
                action_data = self.extract_json_from_response(content)
                return {"success": True, "action": action_data}
            except json.JSONDecodeError as e:
                print(f"JSON decode error in error recovery: {e}")
                return {"success": False, "error": f"Invalid JSON in error recovery: {content[:500]}..."}

        except Exception as e:
            print(f"Error recovery failed: {e}")
            return {"success": False, "error": str(e)}

    async def summarize_html(self, html, task):
        """Summarize HTML into a high-detail English description"""
        try:
            prompt = PROMPTS["summarize_prompt"].format(html=html, task=task)

            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            summary = response.choices[0].message.content.strip()
            return {"success": True, "summary": summary}

        except Exception as e:
            print(f"HTML summarization failed: {e}")
            return {"success": False, "error": str(e)}

    def validate_response(self, response_data):
        """Validate LLM response structure"""
        if not response_data.get("success"):
            return False, response_data.get("error", "Unknown error")

        action = response_data.get("action")
        if not isinstance(action, dict):
            return False, "Action must be a dictionary"

        required_fields = ["action"]
        for field in required_fields:
            if field not in action:
                return False, f"Missing required field: {field}"

        return True, "Valid response"