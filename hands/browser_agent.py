"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Browser Agent: Autonomous Browser Brain          ║
╠══════════════════════════════════════════════════════════════╣
║  A sub-agent with its own LLM loop that controls Chrome      ║
║  via CDP (Chrome DevTools Protocol) — direct websocket.      ║
║                                                              ║
║  No cliclick. No screen coordinates. No monitor bugs.        ║
║  Clicks by selector/text. Types via native input pipeline.   ║
║  Works on any screen setup, any window position.             ║
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
    _activate_chrome, web_search,
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

BROWSER_AGENT_PROMPT = """You are TARS Browser Agent — you control Google Chrome via CDP (Chrome DevTools Protocol).

## CRITICAL RULE: ONLY USE SELECTORS FROM `look` OUTPUT
NEVER guess or assume field names. NEVER use selectors like #firstName, #email, #password unless `look` showed them.
Modern signup pages often use generated IDs like #floatingLabelInput4 or #i0116. You MUST read the `look` output to find the real selectors.

## How to Fill Multi-Step Forms (most signup/login pages work this way)
1. `look` → see what's on the page (usually 1 field at a time)
2. `type` into the EXACT selector shown by `look` 
3. `click` the button shown (use button TEXT like "Next", not "[Next]")
4. `wait` 2 seconds for the page to update
5. `look` again → the page now shows the NEXT field
6. Repeat until done

## Example Workflow
If `look` shows:
  FIELDS:
    Email → #floatingLabelInput4 (email)
  BUTTONS:
    [Next]
Then you do:
  type(selector="#floatingLabelInput4", text="myemail@example.com")
  click(target="Next")
  wait(seconds=2)
  look()
Then if `look` NOW shows:
  FIELDS:
    Password → #floatingLabelInput13 (password)
  BUTTONS:
    [Next]
Then you do:
  type(selector="#floatingLabelInput13", text="MyPassword123")
  click(target="Next")  
  wait(seconds=2)
  look()

## Tools
- **look** — See all interactive elements. ALWAYS do this FIRST and AFTER every action.
- **click** — Click by visible text ("Next", "Sign in") or CSS selector ("#submit"). Use the text WITHOUT brackets.
- **type** — Fill a field using the EXACT CSS selector from `look` output (e.g. `#floatingLabelInput4`)
- **select** — Pick a dropdown option
- **key** — Press keyboard key (enter, tab, escape, etc.)
- **scroll/read/wait/goto/back/forward/refresh/tabs/screenshot/js** — Other tools

## RULES
1. ONLY use selectors from `look`. If `look` shows `Email → #floatingLabelInput4`, use `#floatingLabelInput4`.
2. Fill ONE field at a time. Click the button. Wait. Look. Repeat.
3. If ⚠️ ERRORS/ALERTS appear in `look`, read them and adjust (e.g. "username taken" → try another).
4. NEVER call `done` unless you see a success/welcome page. If still on a form, you're NOT done.
5. If a username is taken, add random numbers and try again.
6. Click buttons by their TEXT (e.g. "Next"), not by "[Next]" with brackets.
7. `js` is READ-ONLY. Never use it to click or modify the page.
8. If stuck after 3+ retries on the same step, call `stuck` with an honest explanation.
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

    def run(self, task, context=None):
        """Execute a browser task autonomously. Returns result dict."""
        print(f"  🌐 Browser Agent: {task[:80]}...")
        self._notify(f"🌐 Starting: {task[:300]}")

        # Make sure Chrome is active
        _activate_chrome()

        # Build initial user message with optional escalation context
        user_msg = f"Complete this task:\n\n{task}"
        if context:
            user_msg += f"\n\n## Additional guidance\n{context}"
        messages = [{"role": "user", "content": user_msg}]
        
        # Track success/error metrics to catch hallucinated success
        total_actions = 0
        total_errors = 0

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
            tools_this_step = 0
            MAX_TOOLS_PER_STEP = 2  # Force step-by-step: ONE action per step

            for block in assistant_content:
                if block.type == "text" and block.text.strip():
                    print(f"    💭 {block.text[:150]}")

                elif block.type == "tool_use":
                    name = block.name
                    inp = block.input
                    tid = block.id
                    
                    # Limit tool calls per step to prevent batching hallucinations
                    tools_this_step += 1
                    if tools_this_step > MAX_TOOLS_PER_STEP:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tid,
                            "content": "SKIPPED: You sent too many actions at once. Do ONE action per step. Your workflow must be: Step 1: look. Step 2: type or click (ONE action). Step 3: wait. Step 4: look again. Never batch multiple actions.",
                        })
                        continue

                    # Terminal tools
                    if name == "done":
                        summary = inp.get("summary", "Done.")
                        # Guard 1: reject if error rate too high
                        if total_actions > 2 and total_errors >= total_actions * 0.5:
                            print(f"  ⚠️ Rejecting 'done' — {total_errors}/{total_actions} actions failed")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tid,
                                "content": f"REJECTED: You cannot claim success — {total_errors} of {total_actions} actions returned errors. Call 'look' to see the current page state, then try a different approach. If truly stuck, call 'stuck' instead.",
                            })
                            continue
                        # Guard 2: reject if 'done' called too early (< 4 actions)
                        if total_actions < 4:
                            print(f"  ⚠️ Rejecting 'done' — only {total_actions} actions taken, too few")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tid,
                                "content": f"REJECTED: Only {total_actions} actions taken — that's too few to have completed a signup/login. Call 'look' to verify the page shows a success/welcome state before calling done.",
                            })
                            continue
                        # Guard 3: verify by checking the current page
                        verify = act_inspect_page()
                        verify_lower = verify.lower()
                        fail_signals = ["signup", "sign up", "create account", "create your", "enter your", "password", "username", "create a", "register", "get started", "floatinglabel"]
                        success_signals = ["welcome", "inbox", "dashboard", "account created", "you're all set", "verify your email", "confirmation", "successfully"]
                        has_fail = any(s in verify_lower for s in fail_signals)
                        has_success = any(s in verify_lower for s in success_signals)
                        if has_fail and not has_success:
                            print(f"  ⚠️ Rejecting 'done' — page still shows signup/form fields")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tid,
                                "content": f"REJECTED: Page still shows signup/login form. Current page:\n{verify[:1500]}\n\nYou are NOT done yet. Continue filling the form or call 'stuck'.",
                            })
                            continue
                        print(f"  ✅ Done: {summary[:150]}")
                        self._notify(f"✅ Done: {summary[:500]}")
                        return {"success": True, "content": summary}

                    if name == "stuck":
                        reason = inp.get("reason", "Unknown.")
                        print(f"  ❌ Stuck: {reason[:150]}")
                        self._notify(f"❌ Stuck: {reason[:500]}")
                        return {"success": False, "stuck": True, "stuck_reason": reason, "content": f"Browser agent stuck: {reason}"}

                    # Execute
                    inp_short = json.dumps(inp)[:100]
                    print(f"    🔧 {name}({inp_short})")
                    result = self._dispatch(name, inp)
                    result_str = str(result)[:4000]
                    print(f"      → {result_str[:150]}")
                    
                    # Track error rate
                    total_actions += 1
                    if result_str.startswith("ERROR"):
                        total_errors += 1
                        # If a type/click failed, show the agent what's ACTUALLY on the page
                        if name in ("type", "click") and "No visible" in result_str:
                            current_page = act_inspect_page()
                            result_str += f"\n\nHere is what is ACTUALLY on the page right now:\n{current_page[:2000]}\n\nUse ONLY the selectors shown above."

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
