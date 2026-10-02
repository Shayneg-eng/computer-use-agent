# Computer Use Agent

An iterated experiment in **computer-use agents** — an LLM that looks at the screen and controls
the mouse/keyboard to accomplish tasks. The folder keeps the full version history so the design
evolution is visible.

## Versions
| Folder | Notes |
|---|---|
| `ComputerUse1.0.0` … `1.1.0` | Early iterations (config-driven) |
| `ComputerUse3.0.0`, `ComputerUse4.0.0` | Later, more capable versions |
| `ComputerUseLocal` | Runs against a local model |
| `ComputerUseVisual1.0.0` | Vision-forward variant |
| `WebToTree` | Maps a web page into a navigable tree for the agent (`agent_flow.py`, `page_map.py`) |

Start from the highest version number (`ComputerUse4.0.0`) for the most complete implementation.

## Setup
Keys are read from the environment (see `.env.example`) — no keys are stored in the code.
```bash
python -m pip install openai pillow
export DEEPSEEK_API_KEY="sk-..."
```

> Automates mouse/keyboard input — run it in an environment you control.
