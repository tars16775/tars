"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Browser Agent: Autonomous Browser Brain          ║
╠══════════════════════════════════════════════════════════════╣
║  A sub-agent with its own LLM loop that controls Chrome      ║
║  using PHYSICAL mouse + keyboard — exactly like a human.     ║
║                                                              ║
║  JS is READ-ONLY (inspect page, find elements).              ║
║  All actions = real mouse clicks + real keyboard typing.     ║
║  Dynamic coordinate mapping — works at any window size.      ║
║                                                              ║
║  Sends iMessage progress updates so user sees what's         ║
║  happening in real time.                                     ║
╚══════════════════════════════════════════════════════════════╝
"""

import json
import time
import subprocess

from hands.browser import (
    act_goto, act_google, act_read_page, act_read_url,
    act_inspect_page, act_fill, act_click, act_select_option,
    act_press_key, act_scroll, act_get_tabs, act_switch_tab,
    act_close_tab, act_new_tab, act_back, act_forward,
    act_refresh, act_wait, act_wait_for_text, act_run_js,
    act_screenshot, act_handle_dialog, _detect_challenge,
    _activate_chrome,
)


# ─────────────────────────────────────────────
#  Tool Definitions — Simple, Human-Like
# ─────────────────────────────────────────────

BROWSER_TOOLS = [
    {
        "name": "look",
        "description": "Look at the current page. Shows all visible fields, buttons, dropdowns, links, and checkboxes with their selectors. ALWAYS do this first before interacting with any page.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "goto",
        "description": "Navigate to a URL.",
        "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
    },
    {
        "name": "click",
        "description": "Physically click on something. Pass either the visible text of a button/link (e.g. 'Next', 'Sign in') or a CSS selector (e.g. '#submit', '.btn'). Uses real mouse click.",
        "input_schema": {"type": "object", "properties": {"target": {"type": "string", "description": "Button/link text like 'Next' or CSS selector like '#myBtn'"}}, "required": ["target"]}
    },
    {
        "name": "type",
        "description": "Click on a field and type text into it physically. Like a human: clicks the field, clears it, types the value.",
        "input_schema": {"type": "object", "properties": {"selector": {"type": "string", "description": "CSS selector of the field from 'look' output, e.g. '#firstName', '[name=email]'"}, "text": {"type": "string", "description": "The text to type"}}, "required": ["selector", "text"]}
    },
    {
        "name": "select",
        "description": "Select an option from ANY dropdown (standard or custom/Material). Clicks the dropdown to open it, then clicks the option. Works with all frameworks.",
        "input_schema": {"type": "object", "properties": {"dropdown": {"type": "string", "description": "The dropdown label text (e.g. 'Month', 'Gender') or CSS selector (e.g. '#month')"}, "option": {"type": "string", "description": "The option text to select (e.g. 'June', 'Male')"}}, "required": ["dropdown", "option"]}
    },
    {
        "name": "key",
        "description": "Press a keyboard key: enter, tab, escape, up, down, left, right, space, backspace, etc.",
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
        "description": "Run custom JavaScript for reading page info. READ-ONLY — never use this to click or modify the page. Use 'return' to get values.",
        "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}
    },
    {
        "name": "done",
        "description": "Task is complete. Provide a summary of what was accomplished.",
        "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}
    },
    {
        "name": "stuck",
        "description": "Cannot complete the task after trying multiple approaches. Explain why.",
        "input_schema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}
    },
]


# ─────────────────────────────────────────────
#  System Prompt
# ─────────────────────────────────────────────

BROWSER_AGENT_PROMPT = """You are TARS Browser Agent — you control Google Chrome on macOS using PHYSICAL mouse clicks and keyboard typing. You interact with web pages exactly like a human would.

## Your Tools (simple, human-like)
- **look** — See all interactive elements on the page (fields, buttons, dropdowns, links). ALWAYS do this first.
- **click** — Physically click a button/link by its text ("Next", "Sign in") or CSS selector ("#submit")
- **type** — Click on an input field and physically type text into it
- **select** — Open a dropdown and pick an option. Works with ANY dropdown type.
- **key** — Press a keyboard key (enter, tab, escape, arrow keys, etc.)
- **scroll/read/wait/goto/back** — Navigation and waiting

## How You Work (like a human)
1. **Look first** — Always call `look` to see what's on the page before acting
2. **Click things** — Use `click` with the button text ("Next", "Create account") 
3. **Type in fields** — Use `type` with the field selector from `look` output (#firstName, [name=email])
4. **Pick dropdowns** — Use `select` with the dropdown label and option text
5. **Wait after actions** — After clicking buttons that submit/navigate, `wait` 2-3 seconds then `look` again

## Important Rules
1. ALWAYS `look` before interacting. Never guess what's on the page.
2. After clicking Next/Submit, ALWAYS `wait` 2-3s then `look` to see the new state.
3. Fill fields ONE AT A TIME with `type`. Don't try to fill multiple at once.
4. For dropdowns, just use `select` — it handles all dropdown types automatically.
5. If something fails, try a different approach. Don't repeat the same action more than twice.
6. If clicking by text fails, try with a CSS selector from `look`. If that fails, try `key` (tab to it + enter).
7. Call `done` when finished. Call `stuck` if you've tried 3+ approaches and nothing works.
8. NEVER use `js` to click buttons, fill fields, or modify the DOM. JS is READ-ONLY for getting info. All actions must be physical.
9. When a page transitions (SPA), content may change without URL changing. Always `look` again.
10. For Google/Material dropdowns: `select` with the label text (e.g. select dropdown="Month" option="June").
"""


# ─────────────────────────────────────────────
#  iMessage Progress (bypass rate limit)
# ─────────────────────────────────────────────

def _send_progress(phone, message):
    """Send a short iMessage progress update."""
    escaped = message.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
    tell application "Messages"
        set targetService to 1st account whose service type = iMessage
        set targetBuddy to participant "{phone}" of targetService
        send "{escaped}" to targetBuddy
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
    except:
        pass


# ─────────────────────────────────────────────
#  Browser Agent Class
# ─────────────────────────────────────────────

class BrowserAgent:
    def __init__(self, llm_client, model, max_steps=40, phone=None):
        self.client = llm_client
        self.model = model
        self.max_steps = max_steps
        self.phone = phone
        self.update_every = 3  # iMessage update every N steps

    def _dispatch(self, name, inp):
        """Route tool calls to browser functions."""
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
            return f"Unknown tool: {name}"
        except Exception as e:
            return f"ERROR: {e}"

    def _notify(self, msg):
        """Send iMessage progress if phone configured."""
        if self.phone:
            _send_progress(self.phone, msg)

    def run(self, task):
        """Execute a browser task autonomously. Returns result dict."""
        print(f"  🌐 Browser Agent: {task[:80]}...")
        self._notify(f"🌐 Starting: {task[:300]}")

        # Make sure Chrome is active
        _activate_chrome()

        messages = [{"role": "user", "content": f"Complete this task:\n\n{task}"}]

        for step in range(1, self.max_steps + 1):
            print(f"  🧠 Step {step}/{self.max_steps}...")

            try:
                response = self.client.create(
                    model=self.model,
                    max_tokens=2048,
                    system=BROWSER_AGENT_PROMPT,
                    tools=BROWSER_TOOLS,
                    messages=messages,
                )
            except Exception as e:
                err = f"API error: {e}"
                print(f"  ❌ {err}")
                self._notify(f"❌ {err[:200]}")
                return {"success": False, "content": err}

            assistant_content = response.content
            tool_results = []

            for block in assistant_content:
                if block.type == "text" and block.text.strip():
                    print(f"    💭 {block.text[:150]}")

                elif block.type == "tool_use":
                    name = block.name
                    inp = block.input
                    tid = block.id

                    # Terminal tools
                    if name == "done":
                        summary = inp.get("summary", "Done.")
                        print(f"  ✅ Done: {summary[:150]}")
                        self._notify(f"✅ Done: {summary[:500]}")
                        return {"success": True, "content": summary}

                    if name == "stuck":
                        reason = inp.get("reason", "Unknown.")
                        print(f"  ❌ Stuck: {reason[:150]}")
                        self._notify(f"❌ Stuck: {reason[:500]}")
                        return {"success": False, "content": f"Stuck: {reason}"}

                    # Execute
                    inp_short = json.dumps(inp)[:100]
                    print(f"    🔧 {name}({inp_short})")
                    result = self._dispatch(name, inp)
                    result_str = str(result)[:4000]
                    print(f"      → {result_str[:150]}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tid,
                        "content": result_str,
                    })

                    # iMessage update every N steps
                    if step % self.update_every == 0:
                        short = result_str[:200] + ("..." if len(result_str) > 200 else "")
                        self._notify(f"🌐 Step {step}: {name}\n→ {short}")

            # No tool calls = prompt to act
            if not tool_results:
                if response.stop_reason == "end_turn":
                    texts = [b.text for b in assistant_content if b.type == "text"]
                    txt = " ".join(texts).strip()
                    if txt:
                        print(f"  ⚠️ Text-only: {txt[:150]}")
                    messages.append({"role": "assistant", "content": assistant_content})
                    messages.append({"role": "user", "content": "Use a tool. If done, call done(). If stuck, call stuck()."})
                    continue

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

        # Max steps hit
        msg = f"Reached {self.max_steps} steps. Task may be partially complete."
        print(f"  ⏱️ {msg}")
        self._notify(f"⏱️ {msg}")
        return {"success": False, "content": msg}
