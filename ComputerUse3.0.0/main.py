#!/usr/bin/env python3
"""
Main orchestration script for autonomous web automation system.
Combines: Website Scanner → Smart Search → Ollama LLM Agent
"""

import asyncio
import sys
import io

# Fix encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from llm.ollama_agent import OllamaLLMAgent


async def interactive_mode():
    """Run in interactive chat mode"""
    print("\n" + "=" * 70)
    print("[WEB] AUTONOMOUS WEB AUTOMATION SYSTEM")
    print("=" * 70)
    print("\nMode: Interactive Chat")
    print("Commands:")
    print("  'scan <url>' - Scan a website")
    print("  'goal <text>' - Run autonomous loop toward a goal")
    print("  'quit' - Exit")
    print("=" * 70)
    
    agent = OllamaLLMAgent(model="qwen3:4b")
    
    while True:
        try:
            user_input = input("\n> You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "quit":
                print("\n[Exit] Goodbye!")
                break
            
            if user_input.lower().startswith("scan "):
                url = user_input[5:].strip()
                await agent.scan_page(url)
                continue
            
            if user_input.lower().startswith("goal "):
                goal = user_input[5:].strip()
                await agent.run_autonomous_loop(goal, max_iterations=3)
                continue
            
            # Regular chat
            await agent.chat(user_input)
        
        except KeyboardInterrupt:
            print("\n\n[Exit] Interrupted by user. Goodbye!")
            break
        except Exception as e:
            print(f"\n[ERROR] Error: {str(e)}")


async def scan_and_analyze(url: str):
    """Scan a URL and provide analysis"""
    print("\n" + "=" * 70)
    print("[SCAN] SCANNING AND ANALYZING")
    print("=" * 70)
    
    agent = OllamaLLMAgent(model="qwen3:4b")
    
    # Scan the page
    await agent.scan_page(url)
    
    # Get analysis
    analysis_prompt = f"""I've scanned {url}. Please provide a comprehensive analysis of:
1. The main buttons and interactive elements available
2. The primary navigation options
3. Key forms or input fields
4. The overall structure of the page"""
    
    await agent.chat(analysis_prompt)


async def autonomous_task(url: str, goal: str):
    """Run an autonomous task toward a goal"""
    print("\n" + "=" * 70)
    print("[TASK] AUTONOMOUS TASK EXECUTION")
    print("=" * 70)
    
    agent = OllamaLLMAgent(model="qwen3:4b")
    
    # Scan the starting page
    await agent.scan_page(url)
    
    # Run autonomous loop
    await agent.run_autonomous_loop(goal, max_iterations=5)


def print_help():
    """Print help message"""
    print("""
AUTONOMOUS WEB AUTOMATION SYSTEM
=================================

Usage: python main.py [MODE] [ARGS]

Modes:

  1. Interactive Mode (default)
     python main.py
     
     Commands in interactive mode:
     - 'scan <url>' - Scan a website and prepare for automation
     - 'goal <text>' - Run autonomous loop toward a goal
     - Normal questions are answered by the LLM
     
  2. Scan and Analyze
     python main.py scan <url>
     Example: python main.py scan https://example.com
     
  3. Autonomous Task
     python main.py task <url> <goal>
     Example: python main.py task https://example.com "Find the login button"

Environment:
  - Ollama must be running with qwen3:4b model
  - Default Ollama URL: http://localhost:11434

Examples:
  # Interactive mode
  python main.py
  
  # Analyze a specific website
  python main.py scan https://news.bbc.com
  
  # Execute a specific task
  python main.py task https://github.com "Find and click the sign up button"
    """)


async def main():
    """Main entry point"""
    
    if len(sys.argv) < 2:
        # Interactive mode
        await interactive_mode()
    else:
        mode = sys.argv[1].lower()
        
        if mode == "help" or mode == "-h" or mode == "--help":
            print_help()
        
        elif mode == "scan":
            if len(sys.argv) < 3:
                print("[ERROR] Usage: python main.py scan <url>")
                sys.exit(1)
            url = sys.argv[2]
            await scan_and_analyze(url)
        
        elif mode == "task":
            if len(sys.argv) < 4:
                print("[ERROR] Usage: python main.py task <url> <goal>")
                sys.exit(1)
            url = sys.argv[2]
            goal = " ".join(sys.argv[3:])
            await autonomous_task(url, goal)
        
        else:
            # Assume it's a URL for quick scan
            if mode.startswith("http://") or mode.startswith("https://"):
                await scan_and_analyze(mode)
            else:
                print(f"[ERROR] Unknown mode: {mode}")
                print_help()
                sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[Exit] Interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[FATAL] Fatal error: {str(e)}")
        sys.exit(1)
