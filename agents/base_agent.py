"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Base Agent: Foundation for All Specialists       ║
╠══════════════════════════════════════════════════════════════╣
║  Every agent (Browser, Coder, System, Research) inherits     ║
║  from this. Provides:                                        ║
║    - Own LLM loop with tool calling                          ║
║    - done / stuck terminal states                            ║
║    - Escalation reporting back to orchestrator               ║
║    - iMessage progress updates                               ║
║    - Step tracking & safety limits                           ║
╚══════════════════════════════════════════════════════════════╝
"""

import json
import time
import subprocess
from abc import ABC, abstractmethod
from utils.event_bus import event_bus


# ─────────────────────────────────────────────
#  iMessage progress helper
# ─────────────────────────────────────────────

def _send_progress(phone, message):
    """Send a short iMessage progress update (bypasses rate limit)."""
    if not phone:
        return
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


class BaseAgent(ABC):
    """
    Base class for all TARS specialist agents.

    Subclasses must implement:
      - agent_name       (str)  — Human-readable name like "Browser Agent"
      - agent_emoji       (str)  — Emoji for logs like "🌐"
      - system_prompt     (str)  — The agent's system prompt
      - tools            (list) — Tool definitions (Anthropic schema)
      - _dispatch(name, inp) → str  — Route tool calls to handlers
    """

    def __init__(self, llm_client, model, max_steps=40, phone=None, update_every=3):
        self.client = llm_client
        self.model = model
        self.max_steps = max_steps
        self.phone = phone
        self.update_every = update_every

    # ── Abstract properties/methods subclasses must implement ──

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Human-readable name: 'Browser Agent', 'Coder Agent', etc."""
        ...

    @property
    @abstractmethod
    def agent_emoji(self) -> str:
        """Emoji for logs: '🌐', '💻', '⚙️', '🔍'"""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """The agent's specialized system prompt."""
        ...

    @property
    @abstractmethod
    def tools(self) -> list:
        """Tool definitions list (Anthropic tool_use schema)."""
        ...

    @abstractmethod
    def _dispatch(self, name: str, inp: dict) -> str:
        """Route a tool call to the actual handler. Return result as string."""
        ...

    # ── Optional hooks subclasses can override ──

    def _on_start(self, task: str):
        """Called before the agent loop starts. Override for setup (e.g., activate Chrome)."""
        pass

    def _on_step(self, step: int, tool_name: str, tool_result: str):
        """Called after each tool execution. Override for per-step logic."""
        pass

    def _on_done(self, summary: str):
        """Called when agent calls done(). Override for cleanup."""
        pass

    def _on_stuck(self, reason: str):
        """Called when agent calls stuck(). Override for cleanup."""
        pass

    # ── Core agent loop ──

    def _notify(self, msg):
        """Send iMessage progress if phone is configured."""
        _send_progress(self.phone, msg)

    def run(self, task, context=None):
        """
        Execute a task autonomously using the agent's LLM loop.

        Args:
            task: The task description
            context: Optional extra context from the orchestrator brain
                     (e.g., previous agent results, brain guidance on stuck)

        Returns:
            dict with keys:
                success (bool)  — Whether the agent completed the task
                content (str)   — Summary or error message
                steps   (int)   — How many steps were taken
                stuck   (bool)  — Whether the agent got stuck (for escalation)
                stuck_reason (str) — Why it got stuck (if stuck=True)
        """
        print(f"  {self.agent_emoji} {self.agent_name}: {task[:80]}...")
        self._notify(f"{self.agent_emoji} {self.agent_name} starting: {task[:300]}")

        # Let subclass do setup
        self._on_start(task)

        # Build initial message with optional context
        user_content = f"Complete this task:\n\n{task}"
        if context:
            user_content += f"\n\n## Additional Context from Brain\n{context}"

        messages = [{"role": "user", "content": user_content}]

        for step in range(1, self.max_steps + 1):
            print(f"  🧠 [{self.agent_name}] Step {step}/{self.max_steps}...")
            event_bus.emit("agent_step", {"agent": self.agent_name.lower().split()[0], "step": step})

            # LLM call with retry for transient Groq errors
            response = None
            last_err = None
            for _api_try in range(3):
                try:
                    response = self.client.create(
                        model=self.model,
                        max_tokens=4096,
                        system=self.system_prompt,
                        tools=self.tools,
                        messages=messages,
                    )
                    break
                except Exception as e:
                    last_err = e
                    err_str = str(e)
                    # Groq tool_use_failed is transient — retry
                    if "tool_use_failed" in err_str or "rate_limit" in err_str.lower():
                        import time as _t
                        _t.sleep(1.0 * (_api_try + 1))
                        print(f"    ⟳ Retrying LLM call ({_api_try + 2}/3)...")
                        continue
                    break  # Non-transient error, stop retrying

            if response is None:
                err = f"API error: {last_err}"
                print(f"  ❌ {err}")
                self._notify(f"❌ {self.agent_name} API error: {str(last_err)[:200]}")
                return {
                    "success": False,
                    "content": err,
                    "steps": step,
                    "stuck": True,
                    "stuck_reason": f"LLM API call failed: {last_err}",
                }

            assistant_content = response.content
            tool_results = []

            for block in assistant_content:
                if block.type == "text" and block.text.strip():
                    print(f"    💭 {block.text[:200]}")

                elif block.type == "tool_use":
                    name = block.name
                    inp = block.input
                    tid = block.id

                    # ── Terminal tool: done ──
                    if name == "done":
                        summary = inp.get("summary", "Done.")
                        print(f"  ✅ [{self.agent_name}] Done: {summary[:200]}")
                        self._notify(f"✅ {self.agent_name} done: {summary[:500]}")
                        self._on_done(summary)
                        return {
                            "success": True,
                            "content": summary,
                            "steps": step,
                            "stuck": False,
                            "stuck_reason": None,
                        }

                    # ── Terminal tool: stuck ──
                    if name == "stuck":
                        reason = inp.get("reason", "Unknown reason.")
                        print(f"  ❌ [{self.agent_name}] Stuck: {reason[:200]}")
                        self._notify(f"⚠️ {self.agent_name} stuck: {reason[:500]}")
                        self._on_stuck(reason)
                        return {
                            "success": False,
                            "content": f"Stuck: {reason}",
                            "steps": step,
                            "stuck": True,
                            "stuck_reason": reason,
                        }

                    # ── Regular tool: dispatch ──
                    inp_short = json.dumps(inp)[:120]
                    print(f"    🔧 {name}({inp_short})")
                    result = self._dispatch(name, inp)
                    result_str = str(result)[:8000]
                    print(f"      → {result_str[:200]}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tid,
                        "content": result_str,
                    })

                    # Callback
                    self._on_step(step, name, result_str)

                    # Periodic progress update
                    if step % self.update_every == 0:
                        short = result_str[:200] + ("..." if len(result_str) > 200 else "")
                        self._notify(f"{self.agent_emoji} Step {step}: {name}\n→ {short}")

            # No tool calls — nudge the agent
            if not tool_results:
                if response.stop_reason == "end_turn":
                    texts = [b.text for b in assistant_content if b.type == "text"]
                    txt = " ".join(texts).strip()
                    if txt:
                        print(f"  ⚠️ [{self.agent_name}] Text-only: {txt[:200]}")
                    messages.append({"role": "assistant", "content": assistant_content})
                    messages.append({
                        "role": "user",
                        "content": "Use a tool to take action. If you're done, call done(summary). If stuck, call stuck(reason)."
                    })
                    continue

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

        # Max steps exhausted
        msg = f"{self.agent_name} reached {self.max_steps} steps without finishing. Task may be partially complete."
        print(f"  ⏱️ {msg}")
        self._notify(f"⏱️ {msg}")
        return {
            "success": False,
            "content": msg,
            "steps": self.max_steps,
            "stuck": True,
            "stuck_reason": f"Reached max {self.max_steps} steps",
        }
