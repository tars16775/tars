"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — System Agent: The Mac Controller                 ║
╠══════════════════════════════════════════════════════════════╣
║  Expert at macOS automation, app control, system tasks.      ║
║  Can open apps, type, click, press keys, run AppleScript,    ║
║  manage files, and run shell commands.                        ║
║                                                              ║
║  Own LLM loop. Inherits from BaseAgent.                      ║
╚══════════════════════════════════════════════════════════════╝
"""

import subprocess

from agents.base_agent import BaseAgent
from agents.agent_tools import (
    TOOL_OPEN_APP, TOOL_TYPE_TEXT, TOOL_KEY_PRESS, TOOL_CLICK,
    TOOL_SCREENSHOT, TOOL_FRONTMOST_APP, TOOL_APPLESCRIPT,
    TOOL_RUN_COMMAND, TOOL_READ_FILE, TOOL_WRITE_FILE, TOOL_LIST_DIR,
    TOOL_DONE, TOOL_STUCK,
)
from hands.mac_control import (
    open_app, type_text, key_press, click, get_frontmost_app, take_screenshot
)
from hands.terminal import run_terminal
from hands.file_manager import read_file, write_file, list_directory


# ─────────────────────────────────────────────
#  System Prompt
# ─────────────────────────────────────────────

SYSTEM_AGENT_PROMPT = """You are TARS System Agent — the world's best macOS automation specialist. You control the Mac like a power user who knows every shortcut, every app, every system trick.

## Your Capabilities
- Open and control any macOS application
- Type text into any active window using physical keyboard
- Press any keyboard shortcut (Cmd+S, Cmd+Shift+P, etc.)
- Click at any screen coordinate using physical mouse
- Take screenshots for visual inspection
- Run raw AppleScript for advanced automation
- Run shell commands for system operations
- Read and write files

## Your Knowledge (macOS Expert)
- Keyboard shortcuts for common apps (VS Code, Finder, Terminal, Safari, etc.)
- System Preferences / Settings navigation
- Finder operations (copy, move, organize files visually)
- Dock, Mission Control, Spotlight usage
- Application-specific AppleScript dictionaries
- Common macOS troubleshooting patterns
- Window management and positioning

## Common Shortcuts You Know
- Cmd+Space → Spotlight
- Cmd+Tab → Switch apps
- Cmd+Q → Quit app
- Cmd+W → Close window
- Cmd+N → New window/document
- Cmd+, → App preferences
- Cmd+Shift+. → Show hidden files in Finder
- Ctrl+Cmd+Q → Lock screen

## Your Process
1. **Check state** — Use `frontmost_app` and `screenshot` to understand what's on screen
2. **Act precisely** — Use the right tool for each action (open_app, type, key_press, click)
3. **Verify** — After each action, check the result (screenshot, frontmost_app)
4. **Adapt** — If an app doesn't respond as expected, try alternatives (AppleScript, keyboard shortcut, etc.)

## Rules
1. Always check what app is active before typing or pressing keys
2. Wait briefly after opening apps (they need time to launch)
3. Use AppleScript for complex automation (controlling specific app features)
4. Take screenshots to verify visual state when needed
5. For file management, prefer shell commands over Finder GUI (more reliable)
6. NEVER run destructive commands without the task explicitly requiring it
7. Call `done` with a clear summary. Call `stuck` with what you tried.
"""


class SystemAgent(BaseAgent):
    """Autonomous system agent — controls macOS like a power user."""

    @property
    def agent_name(self):
        return "System Agent"

    @property
    def agent_emoji(self):
        return "⚙️"

    @property
    def system_prompt(self):
        return SYSTEM_AGENT_PROMPT

    @property
    def tools(self):
        return [
            TOOL_OPEN_APP, TOOL_TYPE_TEXT, TOOL_KEY_PRESS, TOOL_CLICK,
            TOOL_SCREENSHOT, TOOL_FRONTMOST_APP, TOOL_APPLESCRIPT,
            TOOL_RUN_COMMAND, TOOL_READ_FILE, TOOL_WRITE_FILE, TOOL_LIST_DIR,
            TOOL_DONE, TOOL_STUCK,
        ]

    def _dispatch(self, name, inp):
        """Route system tool calls."""
        try:
            if name == "open_app":
                result = open_app(inp["app_name"])
                return result.get("content", str(result))

            elif name == "type_text":
                result = type_text(inp["text"])
                return result.get("content", str(result))

            elif name == "key_press":
                result = key_press(inp["keys"])
                return result.get("content", str(result))

            elif name == "click":
                result = click(inp["x"], inp["y"], inp.get("double_click", False))
                return result.get("content", str(result))

            elif name == "screenshot":
                result = take_screenshot()
                return result.get("content", str(result))

            elif name == "frontmost_app":
                result = get_frontmost_app()
                return result.get("content", str(result))

            elif name == "applescript":
                return self._run_applescript(inp["code"])

            elif name == "run_command":
                result = run_terminal(inp["command"], timeout=inp.get("timeout", 60))
                return result.get("content", str(result))

            elif name == "read_file":
                result = read_file(inp["path"])
                return result.get("content", str(result))

            elif name == "write_file":
                result = write_file(inp["path"], inp["content"])
                return result.get("content", str(result))

            elif name == "list_dir":
                result = list_directory(inp["path"])
                return result.get("content", str(result))

            return f"Unknown system tool: {name}"
        except Exception as e:
            return f"ERROR: {e}"

    def _run_applescript(self, code):
        """Run raw AppleScript and return output."""
        try:
            result = subprocess.run(
                ["osascript", "-e", code],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return result.stdout.strip() or "(no output — script ran successfully)"
            else:
                return f"AppleScript error: {result.stderr.strip()}"
        except subprocess.TimeoutExpired:
            return "AppleScript timed out after 30s"
        except Exception as e:
            return f"AppleScript error: {e}"
