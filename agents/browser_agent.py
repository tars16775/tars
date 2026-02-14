"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Browser Agent: Autonomous Web Expert             ║
╠══════════════════════════════════════════════════════════════╣
║  Controls Google Chrome using PHYSICAL mouse + keyboard.     ║
║  JS is READ-ONLY (inspect page, find elements).              ║
║  All actions = real mouse clicks + real keyboard typing.     ║
║  Dynamic coordinate mapping — works at any window size.      ║
║                                                              ║
║  21 human-like tools. Own LLM loop.                          ║
║  Inherits from BaseAgent.                                    ║
╚══════════════════════════════════════════════════════════════╝
"""

from agents.base_agent import BaseAgent
from agents.agent_tools import TOOL_DONE, TOOL_STUCK

from hands.browser import (
    act_goto, act_google, act_read_page, act_read_url,
    act_inspect_page, act_fill, act_click, act_select_option,
    act_press_key, act_scroll, act_get_tabs, act_switch_tab,
    act_close_tab, act_new_tab, act_back, act_forward,
    act_refresh, act_wait, act_wait_for_text, act_run_js,
    act_screenshot, act_handle_dialog, _activate_chrome,
)


# ─────────────────────────────────────────────
#  Browser-Specific Tool Definitions
# ─────────────────────────────────────────────

BROWSER_TOOLS = [
    {
        "name": "look",
        "description": "Look at the current page. Shows all visible fields, buttons, dropdowns, links, and checkboxes with their selectors. ALWAYS do this first before interacting.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "goto",
        "description": "Navigate to a URL.",
        "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
    },
    {
        "name": "click",
        "description": "Physically click on something. Pass visible text of a button/link ('Next', 'Sign in') or a CSS selector ('#submit', '.btn'). Uses real mouse click.",
        "input_schema": {"type": "object", "properties": {"target": {"type": "string", "description": "Button/link text or CSS selector"}}, "required": ["target"]}
    },
    {
        "name": "type",
        "description": "Click on a field and type text physically. Like a human: clicks the field, clears it, types the value.",
        "input_schema": {"type": "object", "properties": {"selector": {"type": "string", "description": "CSS selector of field, e.g. '#firstName'"}, "text": {"type": "string", "description": "Text to type"}}, "required": ["selector", "text"]}
    },
    {
        "name": "select",
        "description": "Select an option from ANY dropdown (standard or custom/Material). Clicks dropdown to open, then clicks option.",
        "input_schema": {"type": "object", "properties": {"dropdown": {"type": "string", "description": "Dropdown label text or CSS selector"}, "option": {"type": "string", "description": "Option text to select"}}, "required": ["dropdown", "option"]}
    },
    {
        "name": "key",
        "description": "Press a keyboard key: enter, tab, escape, up, down, left, right, space, backspace.",
        "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
    },
    {
        "name": "scroll",
        "description": "Scroll the page: up, down, top, bottom.",
        "input_schema": {"type": "object", "properties": {"direction": {"type": "string", "enum": ["up", "down", "top", "bottom"], "default": "down"}}}
    },
    {
        "name": "read",
        "description": "Read all visible text on the page.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "url",
        "description": "Get the current page URL and title.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "wait",
        "description": "Wait N seconds for page to load or transition.",
        "input_schema": {"type": "object", "properties": {"seconds": {"type": "integer", "default": 2}}}
    },
    {
        "name": "wait_for",
        "description": "Wait for specific text to appear on the page (up to 10s).",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
    },
    {
        "name": "tabs",
        "description": "List all open browser tabs.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "switch_tab",
        "description": "Switch to a specific tab by number.",
        "input_schema": {"type": "object", "properties": {"number": {"type": "integer"}}, "required": ["number"]}
    },
    {
        "name": "close_tab",
        "description": "Close the current tab.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "back",
        "description": "Go back to the previous page.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "forward",
        "description": "Go forward.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "refresh",
        "description": "Reload the current page.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "screenshot",
        "description": "Take a screenshot of the screen for visual inspection.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "js",
        "description": "Run custom JavaScript for reading page info. READ-ONLY — never use to click or modify the DOM. Use 'return' to get values.",
        "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}
    },
    TOOL_DONE,
    TOOL_STUCK,
]


# ─────────────────────────────────────────────
#  System Prompt
# ─────────────────────────────────────────────

BROWSER_SYSTEM_PROMPT = """You are TARS Browser Agent — the world's best web automation specialist. You control Google Chrome on macOS using PHYSICAL mouse clicks and keyboard typing. You interact exactly like a human.

## Your Tools
- **look** — See all interactive elements on the page. ALWAYS do this first.
- **click** — Physically click a button/link by its text ("Next", "Sign in") or CSS selector
- **type** — Click on an input field and physically type text into it
- **select** — Open a dropdown and pick an option. Works with ALL dropdown types.
- **key** — Press a keyboard key (enter, tab, escape, arrow keys)
- **scroll/read/wait/goto/back/forward/refresh** — Navigation
- **tabs/switch_tab/close_tab** — Tab management
- **screenshot** — Visual inspection
- **js** — Read-only JavaScript for getting page info

## Strategy (like a human)
1. **Look first** — ALWAYS `look` before interacting with any page
2. **One action at a time** — Fill fields one at a time, click one button at a time
3. **Verify after actions** — After clicking buttons that submit/navigate, `wait` 2-3s then `look` again
4. **Adapt** — If something fails, try a different approach (text vs CSS selector, tab+enter, etc.)

## Rules
1. ALWAYS `look` before interacting. Never guess what's on the page.
2. After clicking Next/Submit, ALWAYS `wait` 2-3s then `look` to see the new state.
3. Fill fields ONE AT A TIME with `type`.
4. For dropdowns, use `select` — it handles all dropdown types automatically.
5. If clicking by text fails, try CSS selector. If that fails, try `key` (tab + enter).
6. Call `done` when finished. Call `stuck` if you've tried 3+ approaches and nothing works.
7. NEVER use `js` to click, fill, or modify the DOM. JS is READ-ONLY. All actions must be physical.
8. When a page transitions (SPA), content changes without URL changing. Always `look` again.
9. For Google/Material dropdowns: `select` with the label text (e.g., dropdown="Month" option="June").
10. Be efficient — don't waste steps. Every action should make progress.

## CRITICAL ANTI-HALLUCINATION RULES
- NEVER claim you did something you didn't actually do with tools.
- You MUST use tools to perform every action. Saying "I filled the form" without calling `type` is LYING.
- Before calling `done`, VERIFY the result with `look` or `read` — confirm the page shows success.
- Your `done(summary)` MUST describe SPECIFIC actions you took with SPECIFIC tools and what the page showed.
- If you can't complete the task, call `stuck` — NEVER fabricate a success.
- Minimum workflow: goto → look → interact → verify → done. Skipping steps = hallucination.
- If an action returns ERROR, the action FAILED. Do not pretend it succeeded."""


class BrowserAgent(BaseAgent):
    """Autonomous browser agent — controls Chrome physically like a human."""

    @property
    def agent_name(self):
        return "Browser Agent"

    @property
    def agent_emoji(self):
        return "🌐"

    @property
    def system_prompt(self):
        return BROWSER_SYSTEM_PROMPT

    @property
    def tools(self):
        return BROWSER_TOOLS

    def _on_start(self, task):
        """Activate Chrome before starting."""
        _activate_chrome()

    def _dispatch(self, name, inp):
        """Route browser tool calls."""
        try:
            if name == "look":       return act_inspect_page()
            if name == "goto":       return act_goto(inp["url"])
            if name == "click":      return act_click(inp["target"])
            if name == "type":       return act_fill(inp["selector"], inp["text"])
            if name == "select":     return act_select_option(inp["dropdown"], inp["option"])
            if name == "key":        return act_press_key(inp["name"])
            if name == "scroll":     return act_scroll(inp.get("direction", "down"))
            if name == "read":       return act_read_page()
            if name == "url":        return act_read_url()
            if name == "wait":       return act_wait(inp.get("seconds", 2))
            if name == "wait_for":   return act_wait_for_text(inp["text"])
            if name == "tabs":       return act_get_tabs()
            if name == "switch_tab": return act_switch_tab(inp["number"])
            if name == "close_tab":  return act_close_tab()
            if name == "back":       return act_back()
            if name == "forward":    return act_forward()
            if name == "refresh":    return act_refresh()
            if name == "screenshot": return act_screenshot()
            if name == "js":         return act_run_js(inp["code"])
            return f"Unknown browser tool: {name}"
        except Exception as e:
            return f"ERROR: {e}"
