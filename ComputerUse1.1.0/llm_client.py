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
        
    def _attempt_json_repair(self, content):
        """Attempt to repair common JSON formatting issues"""
        try:
            # Remove common prefixes/suffixes
            content = content.strip()
            
            # Remove markdown code block markers if present
            if content.startswith('```'):
                lines = content.split('\n')
                # Remove first line if it's ```json or similar
                if lines[0].startswith('```'):
                    lines = lines[1:]
                # Remove last line if it's ```
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                content = '\n'.join(lines)
            
            # Look for JSON that might be wrapped in text
            lines = content.split('\n')
            json_lines = []
            in_json = False
            
            for line in lines:
                line = line.strip()
                if line.startswith('{'):
                    in_json = True
                    json_lines.append(line)
                elif in_json and line.endswith('}'):
                    json_lines.append(line)
                    break
                elif in_json:
                    json_lines.append(line)
            
            if json_lines:
                candidate = '\n'.join(json_lines)
                # Basic validation - should start with { and end with }
                candidate = candidate.strip()
                if candidate.startswith('{') and candidate.endswith('}'):
                    return candidate
            
            # Try to extract just the JSON part if mixed with other text
            import re
            # Look for patterns like: some text {"action": ...} more text
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
            if json_match:
                return json_match.group(0)
                
        except Exception as e:
            print(f"JSON repair attempt failed: {e}")
            return None
        
        return None

    def extract_json_from_response(self, content):
        """Extract JSON from LLM response that may contain markdown or other text"""
        if not content or not isinstance(content, str):
            raise json.JSONDecodeError(f"Empty or invalid content: {content}")
        
        # Clean up the content first
        content = content.strip()
        
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
        # More robust pattern that handles nested braces
        brace_count = 0
        start_idx = -1
        
        for i, char in enumerate(content):
            if char == '{':
                if start_idx == -1:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    # Found complete JSON object
                    json_candidate = content[start_idx:i+1]
                    try:
                        return json.loads(json_candidate)
                    except json.JSONDecodeError:
                        # Continue looking for other JSON objects
                        start_idx = -1
                        continue
        
        # Try to fix common JSON issues
        fixed_content = self._attempt_json_repair(content)
        if fixed_content:
            try:
                return json.loads(fixed_content)
            except json.JSONDecodeError:
                pass
        
        # If no valid JSON found, raise an error with more context
        raise json.JSONDecodeError(f"No valid JSON found in response. Content preview: {content[:500]}...")

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

            content = response.choices[0].message.content
            if not content:
                return {"success": False, "error": "Empty response from LLM"}
                
            content = content.strip()
            print(f"Raw LLM Response: {repr(content)}")  # Use repr to see exact content

            # Extract JSON from response
            try:
                action_data = self.extract_json_from_response(content)
                return {"success": True, "action": action_data}
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                # Try one more repair attempt with the full content
                print(f"Full response content for debugging:\n{content}")
                return {"success": False, "error": f"Invalid JSON response. Response was: {content[:200]}..."}

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

    async def summarize_html(self, html, task, change_context=""):
        """Summarize HTML into a high-detail English description with change context"""
        try:
            # Build the prompt with change context
            if change_context:
                context_section = f"**IMPORTANT CONTEXT**: {change_context}\n\n"
            else:
                context_section = ""
            
            prompt = PROMPTS["summarize_prompt"].format(
                html=html, 
                task=task,
                change_context=context_section
            )

            messages = [
                {"role": "system", "content": "You are a helpful assistant that analyzes web content for browser automation."},
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