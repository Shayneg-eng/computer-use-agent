import json
import asyncio
from typing import Optional, Dict, Any
from ollama import AsyncClient

# Import other modules
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.smart_search import SmartSearch
from scanner.website_scanner import WebsiteScanner

class OllamaLLMAgent:
    """
    Autonomous agent that uses Ollama LLM with qwen model for web automation.
    Integrates website scanning, smart search, and LLM decision-making.
    """
    
    def __init__(self, model: str = "qwen3:4b", base_url: str = "http://localhost:11434"):
        self.client = AsyncClient(host=base_url)
        self.model = model
        self.scanner = WebsiteScanner()
        self.conversation_history = []
        self.page_info = None
        
        print(f"[LLM] Initialized Ollama Agent with model: {model}")
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for the LLM with available tools"""
        return """You are an autonomous web automation agent. Your role is to:
1. Analyze web pages and extract key information
2. Search for specific elements (buttons, links, inputs)
3. Decide what actions to take based on user goals
4. Provide clear explanations of your actions

Available functions you can use:
- search_buttons(query): Find buttons by text
- search_links(query): Find links by text or URL
- search_inputs(query): Find input fields by label
- search_text(query): Find text content
- get_page_overview(): Get page statistics
- scan_page(url): Scan a new URL and extract page information

When responding, if you need to search for something, format your response clearly stating what you found.
Always provide structured responses with the actions you recommend."""
    
    async def search_buttons(self, query: str) -> list:
        """Search for buttons on the current page"""
        results = SmartSearch.search_buttons(query)
        return results
    
    async def search_links(self, query: str) -> list:
        """Search for links on the current page"""
        results = SmartSearch.search_links(query)
        return results
    
    async def search_inputs(self, query: str) -> list:
        """Search for input fields on the current page"""
        results = SmartSearch.search_inputs(query)
        return results
    
    async def search_text(self, query: str) -> list:
        """Search for text content on the current page"""
        results = SmartSearch.search_text(query)
        return results
    
    async def get_page_overview(self) -> dict:
        """Get overview of current page"""
        overview = SmartSearch.get_page_overview()
        return overview or {"error": "No page scanned yet"}
    
    async def scan_page(self, url: str) -> dict:
        """Scan a new URL"""
        print(f"\n[SCAN] Scanning {url}...")
        await self.scanner.scan_website(url)
        self.page_info = SmartSearch.get_page_overview()
        return {
            "status": "success",
            "url": url,
            "page_info": self.page_info
        }
    
    def format_tool_response(self, tool_name: str, result: Any) -> str:
        """Format tool response for LLM"""
        if isinstance(result, list):
            if not result:
                return f"No results found for {tool_name}"
            return json.dumps(result, indent=2, ensure_ascii=False)
        elif isinstance(result, dict):
            return json.dumps(result, indent=2, ensure_ascii=False)
        return str(result)
    
    async def process_llm_response(self, response: str) -> Dict[str, Any]:
        """Process LLM response and extract tool calls if any"""
        import re
        result = {
            "response": response,
            "tool_calls": [],
            "actions": []
        }
        
        # Extract all potential function calls using flexible regex patterns
        # Matches: function_name("text"), function_name('text'), function_name(text)
        pattern = r'(\w+)\s*\(\s*["\']?([^"\')\]]+)["\']?\s*\)'
        matches = re.findall(pattern, response)
        
        for func_name, query in matches:
            if func_name == "search_buttons" and "search_buttons" not in [tc["tool"] for tc in result["tool_calls"]]:
                buttons = await self.search_buttons(query.strip())
                result["tool_calls"].append({
                    "tool": "search_buttons",
                    "query": query.strip(),
                    "result": buttons
                })
            
            elif func_name == "search_links" and "search_links" not in [tc["tool"] for tc in result["tool_calls"]]:
                links = await self.search_links(query.strip())
                result["tool_calls"].append({
                    "tool": "search_links",
                    "query": query.strip(),
                    "result": links
                })
            
            elif func_name == "search_inputs" and "search_inputs" not in [tc["tool"] for tc in result["tool_calls"]]:
                inputs = await self.search_inputs(query.strip())
                result["tool_calls"].append({
                    "tool": "search_inputs",
                    "query": query.strip(),
                    "result": inputs
                })
            
            elif func_name == "search_text" and "search_text" not in [tc["tool"] for tc in result["tool_calls"]]:
                texts = await self.search_text(query.strip())
                result["tool_calls"].append({
                    "tool": "search_text",
                    "query": query.strip(),
                    "result": texts
                })
        
        # Also check for get_page_overview (has no parameters)
        if "get_page_overview" in response and "get_page_overview" not in [tc["tool"] for tc in result["tool_calls"]]:
            overview = await self.get_page_overview()
            result["tool_calls"].append({
                "tool": "get_page_overview",
                "result": overview
            })
        
        return result
    
    async def chat(self, user_message: str) -> str:
        """
        Send a message to the Ollama LLM and get response with tool integration.
        
        Args:
            user_message: The user's message/instruction
            
        Returns:
            The LLM's response
        """
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Prepare messages for API
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            *self.conversation_history
        ]
        
        print(f"\n[INPUT] User: {user_message}")
        
        try:
            # Call Ollama API
            response = await self.client.chat(
                model=self.model,
                messages=messages,
                stream=False
            )
            
            assistant_message = response["message"]["content"]
            
            # Process response for tool calls BEFORE adding to history
            processed = await self.process_llm_response(assistant_message)
            
            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            # If tools were executed, add their results to history for next iteration
            if processed["tool_calls"]:
                tool_summary_lines = []
                for call in processed["tool_calls"]:
                    tool_name = call['tool']
                    result = call.get('result', [])
                    
                    # Handle both list and dict results
                    if isinstance(result, list):
                        count = len(result)
                        summary = json.dumps(result[:3], ensure_ascii=False) if result else "[]"
                    elif isinstance(result, dict):
                        count = len(result)
                        summary = json.dumps(result, ensure_ascii=False)
                    else:
                        count = 0
                        summary = str(result)
                    
                    tool_summary_lines.append(f"Tool '{tool_name}': Found {count} results")
                
                tool_summary = "\n".join(tool_summary_lines)
                self.conversation_history.append({
                    "role": "user",
                    "content": f"[Tool Execution Results]\n{tool_summary}"
                })
            
            # Print response
            print(f"\n[LLM] Agent: {assistant_message}")
            
            # Print any tool calls results
            if processed["tool_calls"]:
                print("\n[TOOLS] Tool Results:")
                for tool_call in processed["tool_calls"]:
                    result = tool_call.get('result', [])
                    if isinstance(result, list):
                        num_results = len(result)
                    elif isinstance(result, dict):
                        num_results = len(result)
                    else:
                        num_results = 0
                    
                    print(f"  - {tool_call['tool']}: {num_results} results")
                    if num_results > 0 and isinstance(result, (list, dict)):
                        if isinstance(result, list):
                            print(f"    Sample: {result[0]}")
                        else:
                            print(f"    Result: {result}")
            
            return assistant_message
        
        except Exception as e:
            error_msg = f"[ERROR] Error communicating with Ollama: {str(e)}"
            print(error_msg)
            return error_msg
    
    async def run_autonomous_loop(self, goal: str, max_iterations: int = 5):
        """
        Run an autonomous loop where the agent works toward a goal.
        
        Args:
            goal: The goal to achieve
            max_iterations: Maximum iterations before stopping
        """
        print(f"\n[TASK] Starting autonomous loop for goal: {goal}")
        print("=" * 60)
        
        # First, scan the current page if not already done
        if not self.page_info:
            # Assume we're on a known URL for now
            await self.scan_page("https://google.com")
        
        for iteration in range(max_iterations):
            print(f"\n[ITER] Iteration {iteration + 1}/{max_iterations}")
            
            if iteration == 0:
                # First message with the goal
                message = f"Goal: {goal}\n\nPlease analyze the current page and tell me what steps you would take to achieve this goal."
            else:
                # Follow-up based on previous actions
                message = f"Continue working toward the goal: {goal}\n\nWhat should we do next?"
            
            response = await self.chat(message)
            
            # Check if goal is achieved (simple check)
            if "completed" in response.lower() or "achieved" in response.lower() or "done" in response.lower():
                print("\n[OK] Goal appears to be achieved!")
                break
            
            await asyncio.sleep(1)  # Brief pause between iterations
        
        print("\n" + "=" * 60)
        print("[DONE] Autonomous loop completed")


async def main():
    """Example usage of the Ollama agent"""
    
    # Initialize agent
    agent = OllamaLLMAgent(model="qwen3:4b")
    
    # Example 1: Scan a page
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Scanning a page")
    print("=" * 60)
    await agent.scan_page("https://example.com")
    
    # Example 2: Query the page
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Interactive chat")
    print("=" * 60)
    await agent.chat("What buttons are available on this page?")
    
    # Example 3: Search for something
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Searching for links")
    print("=" * 60)
    await agent.chat("Find all links related to navigation")


if __name__ == "__main__":
    asyncio.run(main())
