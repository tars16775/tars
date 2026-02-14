"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Escalation Engine: Smart Failure Recovery        ║
╠══════════════════════════════════════════════════════════════╣
║  When an agent gets stuck, this engine:                       ║
║    1. Analyzes WHY it got stuck                              ║
║    2. Retries with brain guidance (better instructions)      ║
║    3. Reroutes to a different agent                          ║
║    4. Decomposes into smaller sub-tasks                      ║
║    5. Asks the user via iMessage as last resort              ║
║                                                              ║
║  Keeps a failure log so it never retries the same approach.  ║
╚══════════════════════════════════════════════════════════════╝
"""

import time
from datetime import datetime


class EscalationManager:
    """Manages the escalation chain when agents get stuck."""

    # Which agents can be rerouted to for which task types
    REROUTE_MAP = {
        "browser": [],                         # Browser tasks MUST stay browser-only. NO rerouting — other agents can't browse.
        "coder":   ["system"],                  # If coder fails, system might handle it with raw commands
        "system":  ["coder"],                   # If system fails, coder might script it
        "research": ["browser"],               # If research fails, browser can do manual browsing
        "file":    ["coder", "system"],        # If file agent fails, coder or system can handle
    }

    def __init__(self, max_retries=3):
        self.max_retries = max_retries
        self.failure_log = []  # List of {agent, task, reason, strategy, timestamp}

    def handle_stuck(self, agent_name, task, stuck_reason, attempt=1):
        """
        Determine the best escalation strategy.

        Args:
            agent_name: Which agent got stuck ("browser", "coder", etc.)
            task: The original task description
            stuck_reason: Why the agent got stuck
            attempt: Which attempt this is (1, 2, 3, 4)

        Returns:
            dict with:
                strategy: "retry" | "reroute" | "decompose" | "ask_user"
                agent: Which agent to use (for retry/reroute)
                context: Guidance to give the agent
                message: Human-readable explanation
        """
        # Log the failure
        self.failure_log.append({
            "agent": agent_name,
            "task": task[:200],
            "reason": stuck_reason[:500],
            "attempt": attempt,
            "timestamp": datetime.now().isoformat(),
        })

        # ── Strategy 1: Retry same agent with guidance ──
        if attempt == 1:
            guidance = self._generate_retry_guidance(agent_name, task, stuck_reason)
            return {
                "strategy": "retry",
                "agent": agent_name,
                "context": guidance,
                "message": f"⟳ Retrying {agent_name} with additional guidance based on failure analysis.",
            }

        # ── Strategy 2: Reroute to different agent ──
        if attempt == 2:
            alt_agent = self._find_alternative_agent(agent_name, task, stuck_reason)
            if alt_agent:
                return {
                    "strategy": "reroute",
                    "agent": alt_agent,
                    "context": f"Previous attempt by {agent_name} failed: {stuck_reason}\n\nTry a different approach to accomplish: {task}",
                    "message": f"🔀 Rerouting from {agent_name} to {alt_agent} for a different approach.",
                }
            # No alternative — fall through to decompose
            return self.handle_stuck(agent_name, task, stuck_reason, attempt=3)

        # ── Strategy 3: Decompose into smaller sub-tasks ──
        if attempt == 3:
            return {
                "strategy": "decompose",
                "agent": agent_name,
                "context": f"The full task failed. Try breaking it into smaller steps and doing the parts you CAN do.\n\nOriginal task: {task}\nPrevious failure: {stuck_reason}\n\nDo whatever partial work is possible and report what you accomplished vs what you couldn't do.",
                "message": f"🔧 Decomposing task into smaller pieces for {agent_name}.",
            }

        # ── Strategy 4: Ask user via iMessage ──
        return {
            "strategy": "ask_user",
            "agent": None,
            "context": None,
            "message": self._build_user_message(agent_name, task, stuck_reason),
        }

    def _generate_retry_guidance(self, agent_name, task, stuck_reason):
        """Generate specific guidance based on failure analysis."""
        guidance_parts = [
            f"Your previous attempt failed with this reason: {stuck_reason}",
            "",
            "Guidance for retry:",
        ]

        reason_lower = stuck_reason.lower()

        # Browser-specific guidance
        if agent_name == "browser":
            guidance_parts.append("- CRITICAL: Call 'look' first to see what's ACTUALLY on the page")
            guidance_parts.append("- ONLY use selectors from the 'look' output — never guess selector names")
            guidance_parts.append("- Many signup forms show ONE field at a time. Fill it, click Next, then look again.")
            if "click" in reason_lower or "button" in reason_lower:
                guidance_parts.append("- Use the button's visible text like 'Next' — not '[Next]'")
                guidance_parts.append("- Try using tab + enter to navigate to and activate the element")
            if "timeout" in reason_lower or "load" in reason_lower:
                guidance_parts.append("- Wait longer between actions (3-5 seconds)")
                guidance_parts.append("- Check if the page URL changed — you might be on a different page")
            if "error" in reason_lower:
                guidance_parts.append("- Check ⚠️ ERRORS/ALERTS in the 'look' output for page error messages")
                guidance_parts.append("- If a username is taken, try a different one with random numbers")
            if "dropdown" in reason_lower or "select" in reason_lower:
                guidance_parts.append("- Use the 'select' tool with the dropdown label text, not CSS selector")
                guidance_parts.append("- Try scrolling down to see if the dropdown options are below the fold")
            if "captcha" in reason_lower:
                guidance_parts.append("- CAPTCHAs cannot be solved automatically. Report this to the user.")

        # Coder-specific guidance
        elif agent_name == "coder":
            if "error" in reason_lower or "traceback" in reason_lower:
                guidance_parts.append("- Read the full error message carefully")
                guidance_parts.append("- Read the relevant file to understand the context")
                guidance_parts.append("- Check if there are missing imports or dependencies")
            if "permission" in reason_lower:
                guidance_parts.append("- Try using sudo if appropriate")
                guidance_parts.append("- Check file permissions with ls -la")
            if "not found" in reason_lower:
                guidance_parts.append("- Search for the correct file/path using search_files")
                guidance_parts.append("- Check if the dependency is installed")

        # System-specific guidance
        elif agent_name == "system":
            if "app" in reason_lower:
                guidance_parts.append("- Make sure the app name is exact (case-sensitive)")
                guidance_parts.append("- Try using 'open -a AppName' via run_command instead")
            if "click" in reason_lower:
                guidance_parts.append("- Take a screenshot first to verify coordinates")
                guidance_parts.append("- Try keyboard shortcuts instead of clicking")

        # Generic guidance
        guidance_parts.append("- Try a completely different approach than what you tried before")
        guidance_parts.append("- If the same method fails twice, it won't work a third time — change strategy")

        return "\n".join(guidance_parts)

    def _find_alternative_agent(self, failed_agent, task, reason):
        """Find an alternative agent that might handle the task."""
        alternatives = self.REROUTE_MAP.get(failed_agent, [])

        # Check if we already failed with this alternative
        failed_agents = {f["agent"] for f in self.failure_log if f["task"][:100] == task[:100]}

        for alt in alternatives:
            if alt not in failed_agents:
                return alt

        return None  # No untried alternatives

    def _build_user_message(self, agent_name, task, reason):
        """Build a clear iMessage to the user about the failure."""
        # Collect all attempts
        relevant = [f for f in self.failure_log if f["task"][:100] == task[:100]]
        attempts_summary = "\n".join(
            f"  {i+1}. {f['agent']}: {f['reason'][:100]}"
            for i, f in enumerate(relevant[-4:])
        )

        return (
            f"⚠️ TARS needs help\n\n"
            f"Task: {task[:300]}\n\n"
            f"I tried {len(relevant)} approaches:\n{attempts_summary}\n\n"
            f"Last error: {reason[:300]}\n\n"
            f"What should I do? Reply with instructions or 'skip' to move on."
        )

    def clear_log(self):
        """Clear failure log (e.g., after successful task)."""
        self.failure_log = []

    def get_stats(self):
        """Get escalation statistics."""
        if not self.failure_log:
            return {"total_failures": 0, "agents": {}}

        agent_failures = {}
        for f in self.failure_log:
            agent = f["agent"]
            agent_failures[agent] = agent_failures.get(agent, 0) + 1

        return {
            "total_failures": len(self.failure_log),
            "agents": agent_failures,
            "last_failure": self.failure_log[-1] if self.failure_log else None,
        }
