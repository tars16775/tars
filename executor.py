"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Orchestrator Executor                            ║
╠══════════════════════════════════════════════════════════════╣
║  Routes the brain's tool calls to agent deployments and      ║
║  direct handlers. Tracks ALL deployments so the brain sees   ║
║  what already failed and can make smarter decisions.         ║
║                                                              ║
║  Key design: The executor NEVER silently retries the same    ║
║  thing. Every failure goes back to the brain with full       ║
║  context so the LLM can reason about the next move.          ║
╚══════════════════════════════════════════════════════════════╝
"""

from brain.llm_client import LLMClient
from brain.self_improve import SelfImproveEngine
from agents.browser_agent import BrowserAgent
from agents.coder_agent import CoderAgent
from agents.system_agent import SystemAgent
from agents.research_agent import ResearchAgent
from agents.file_agent import FileAgent
from agents.comms import agent_comms
from memory.agent_memory import AgentMemory
from hands.terminal import run_terminal
from hands.file_manager import read_file
from hands.browser import act_google as browser_google
from utils.event_bus import event_bus
from utils.agent_monitor import agent_monitor


# Agent class registry
AGENT_CLASSES = {
    "browser": BrowserAgent,
    "coder": CoderAgent,
    "system": SystemAgent,
    "research": ResearchAgent,
    "file": FileAgent,
}

# Hard limit: max agent deployments per brain task cycle
MAX_DEPLOYMENTS_PER_TASK = 6


class ToolExecutor:
    def __init__(self, config, imessage_sender, imessage_reader, memory_manager, logger):
        self.config = config
        self.sender = imessage_sender
        self.reader = imessage_reader
        self.memory = memory_manager
        self.logger = logger
        self.comms = agent_comms
        self.monitor = agent_monitor

        # ── Deployment tracker — resets per task ──
        # Every deployment and its result, so brain sees full history
        self._deployment_log = []  # [{agent, task, success, steps, reason}]

        # LLM client for agents
        llm_cfg = config["llm"]
        self.llm_client = LLMClient(
            provider=llm_cfg["provider"],
            api_key=llm_cfg["api_key"],
            base_url=llm_cfg.get("base_url"),
        )
        self.heavy_model = llm_cfg["heavy_model"]
        self.fast_model = llm_cfg.get("fast_model", self.heavy_model)
        self.phone = config["imessage"]["owner_phone"]

        # Agent memory + self-improvement engine
        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.agent_memory = AgentMemory(base_dir)
        self.self_improve = SelfImproveEngine(
            agent_memory=self.agent_memory,
            llm_client=self.llm_client,
            model=self.fast_model,
        )

    def reset_task_tracker(self):
        """Call this when a new user task starts (from tars.py)."""
        self._deployment_log = []

    def _get_failure_summary(self):
        """Build a summary of all failed deployments this task for the brain to see."""
        failures = [d for d in self._deployment_log if not d["success"]]
        if not failures:
            return ""
        lines = ["## ⚠️ PREVIOUS FAILED ATTEMPTS THIS TASK:"]
        for i, f in enumerate(failures, 1):
            lines.append(f"  {i}. [{f['agent']}] task='{f['task'][:100]}' → FAILED ({f['steps']} steps): {f['reason'][:200]}")
        lines.append("")
        lines.append("DO NOT repeat the same approach. Analyze WHY each failed and try something DIFFERENT.")
        return "\n".join(lines)

    def execute(self, tool_name, tool_input):
        """Execute a tool call and return the result."""
        self.logger.info(f"🔧 {tool_name} → {str(tool_input)[:120]}")

        try:
            result = self._dispatch(tool_name, tool_input)
        except Exception as e:
            result = {"success": False, "error": True, "content": f"Tool execution error: {e}"}

        # Log to memory
        self.memory.log_action(tool_name, tool_input, result)

        # Log result
        status = "✅" if result.get("success") else "❌"
        self.logger.info(f"  {status} {str(result.get('content', ''))[:120]}")

        return result

    def _dispatch(self, tool_name, inp):
        """Route tool call to the right handler."""

        # ─── Agent Deployments ───────────────────
        if tool_name == "deploy_browser_agent":
            return self._deploy_agent("browser", inp["task"])

        elif tool_name == "deploy_coder_agent":
            return self._deploy_agent("coder", inp["task"])

        elif tool_name == "deploy_system_agent":
            return self._deploy_agent("system", inp["task"])

        elif tool_name == "deploy_research_agent":
            return self._deploy_agent("research", inp["task"])

        elif tool_name == "deploy_file_agent":
            return self._deploy_agent("file", inp["task"])

        # ─── Direct Tools ────────────────────────
        elif tool_name == "send_imessage":
            event_bus.emit("imessage_sent", {"message": inp["message"]})
            return self.sender.send(inp["message"])

        elif tool_name == "wait_for_reply":
            result = self.reader.wait_for_reply(timeout=inp.get("timeout", 300))
            if result.get("success"):
                event_bus.emit("imessage_received", {"message": result.get("content", "")})
            return result

        elif tool_name == "save_memory":
            return self.memory.save(inp["category"], inp["key"], inp["value"])

        elif tool_name == "recall_memory":
            return self.memory.recall(inp["query"])

        elif tool_name == "run_quick_command":
            return run_terminal(inp["command"], timeout=inp.get("timeout", 30))

        elif tool_name == "quick_read_file":
            return read_file(inp["path"])

        elif tool_name == "think":
            thought = inp["thought"]
            self.logger.info(f"💭 Brain thinking: {thought[:200]}")
            event_bus.emit("thinking", {"text": thought, "model": "brain"})
            return {"success": True, "content": "Thought recorded. Continue with your plan."}

        # ─── Legacy tool names ──
        elif tool_name == "web_task":
            return self._deploy_agent("browser", inp["task"])

        elif tool_name == "web_search":
            text = browser_google(inp["query"])
            return {"success": True, "content": text if isinstance(text, str) else str(text)}

        else:
            return {"success": False, "error": True, "content": f"Unknown tool: {tool_name}"}

    def _deploy_agent(self, agent_type, task):
        """
        Deploy a specialist agent. No hidden retry loops.
        
        If the agent succeeds → return success to brain.
        If the agent gets stuck → return the failure WITH full context 
        of all previous failures so the brain can make a smarter decision.
        
        The BRAIN decides what to do next, not the executor.
        """
        agent_class = AGENT_CLASSES.get(agent_type)
        if not agent_class:
            return {"success": False, "error": True, "content": f"Unknown agent type: {agent_type}"}

        # ── Hard limit: prevent infinite deployment loops ──
        deployment_count = len(self._deployment_log)
        if deployment_count >= MAX_DEPLOYMENTS_PER_TASK:
            failures = self._get_failure_summary()
            return {
                "success": False,
                "error": True,
                "content": (
                    f"DEPLOYMENT LIMIT REACHED ({MAX_DEPLOYMENTS_PER_TASK} agents deployed this task). "
                    f"You MUST ask Abdullah for help via send_imessage now.\n\n"
                    f"{failures}"
                ),
            }

        # ── Build context from previous failures + memory ──
        context_parts = []

        # Previous failure history (most important — prevents repeating mistakes)
        failure_summary = self._get_failure_summary()
        if failure_summary:
            context_parts.append(failure_summary)

        # Memory advice from past tasks
        memory_context = self.self_improve.get_pre_task_advice(agent_type, task)
        if memory_context:
            context_parts.append(f"## Learned from past tasks\n{memory_context}")

        # Handoff from another agent
        handoff = self.comms.get_handoff_context(agent_type)
        if handoff:
            context_parts.append(handoff)

        context = "\n\n".join(context_parts) if context_parts else None

        # ── Emit events ──
        attempt = deployment_count + 1
        event_bus.emit("agent_started", {
            "agent": agent_type,
            "task": task[:200],
            "attempt": attempt,
        })
        self.monitor.on_started(agent_type, task[:200], attempt)
        self.logger.info(f"🚀 Deploying {agent_type} agent (deployment {attempt}/{MAX_DEPLOYMENTS_PER_TASK}): {task[:100]}")

        # ── Create and run the agent ──
        agent = agent_class(
            llm_client=self.llm_client,
            model=self.heavy_model,
            max_steps=40,
            phone=self.phone,
        )

        result = agent.run(task, context=context)

        # ── Record this deployment ──
        entry = {
            "agent": agent_type,
            "task": task[:300],
            "success": result.get("success", False),
            "steps": result.get("steps", 0),
            "reason": result.get("stuck_reason") or result.get("content", "")[:300],
        }
        self._deployment_log.append(entry)

        # ── Record in self-improvement engine ──
        self.self_improve.record_task_outcome(
            agent_name=agent_type,
            task=task,
            result=result,
            escalation_history=[],
        )

        # ── Handoff context on success ──
        if result.get("success"):
            self.comms.send(
                from_agent=agent_type,
                to_agent="brain",
                content=result.get("content", "")[:500],
                msg_type="result",
            )

        # ── Emit completion ──
        event_bus.emit("agent_completed", {
            "agent": agent_type,
            "success": result.get("success", False),
            "steps": result.get("steps", 0),
            "stuck": result.get("stuck", False),
        })
        self.monitor.on_completed(agent_type, result.get("success", False), result.get("steps", 0))

        # ── If failed, enrich the result so brain sees everything ──
        if not result.get("success"):
            stuck_reason = result.get("stuck_reason", result.get("content", "Unknown"))
            self.logger.warning(f"⚠️ {agent_type} agent stuck: {stuck_reason[:200]}")

            # Build rich failure response for the brain
            all_failures = self._get_failure_summary()
            remaining = MAX_DEPLOYMENTS_PER_TASK - len(self._deployment_log)

            result["content"] = (
                f"❌ {agent_type} agent FAILED after {result.get('steps', 0)} steps.\n"
                f"Reason: {stuck_reason[:400]}\n\n"
                f"{all_failures}\n\n"
                f"You have {remaining} agent deployments remaining this task. "
                f"THINK about WHY this failed before deploying again. "
                f"Consider: (1) deploy same agent with DIFFERENT, MORE SPECIFIC instructions, "
                f"(2) break the task into smaller steps and deploy for just the FIRST step, "
                f"(3) ask Abdullah for help via send_imessage."
            )

        return result
