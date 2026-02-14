"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Orchestrator Executor                            ║
╠══════════════════════════════════════════════════════════════╣
║  Routes the brain's tool calls to agent deployments and      ║
║  direct handlers. Manages the escalation chain when agents   ║
║  get stuck.                                                  ║
║                                                              ║
║  The brain deploys agents → executor launches them →         ║
║  agents run autonomously → results flow back to brain.       ║
╚══════════════════════════════════════════════════════════════╝
"""

from brain.llm_client import LLMClient
from brain.escalation import EscalationManager
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


class ToolExecutor:
    def __init__(self, config, imessage_sender, imessage_reader, memory_manager, logger):
        self.config = config
        self.sender = imessage_sender
        self.reader = imessage_reader
        self.memory = memory_manager
        self.logger = logger
        self.escalation = EscalationManager(max_retries=config["safety"]["max_retries"])
        self.comms = agent_comms
        self.monitor = agent_monitor

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
            # Think tool — just log and return (brain processes internally)
            thought = inp["thought"]
            self.logger.info(f"💭 Brain thinking: {thought[:200]}")
            event_bus.emit("thinking", {"text": thought, "model": "brain"})
            return {"success": True, "content": f"Thought recorded. Continue with your plan."}

        # ─── Legacy tool names (backward compatibility) ──
        elif tool_name == "web_task":
            return self._deploy_agent("browser", inp["task"])

        elif tool_name == "web_search":
            text = browser_google(inp["query"])
            return {"success": True, "content": text if isinstance(text, str) else str(text)}

        else:
            return {"success": False, "error": True, "content": f"Unknown tool: {tool_name}"}

    def _deploy_agent(self, agent_type, task, context=None, attempt=1):
        """
        Deploy a specialist agent. Handles escalation if agent gets stuck.

        Args:
            agent_type: "browser", "coder", "system", "research", "file"
            task: The task description
            context: Optional guidance from escalation manager
            attempt: Current attempt number (for escalation chain)
        """
        agent_class = AGENT_CLASSES.get(agent_type)
        if not agent_class:
            return {"success": False, "error": True, "content": f"Unknown agent type: {agent_type}"}

        # ── Pre-task: get memory advice ──
        memory_context = self.self_improve.get_pre_task_advice(agent_type, task)
        if memory_context and context:
            context = f"{context}\n\n## Learned from past tasks\n{memory_context}"
        elif memory_context:
            context = f"## Learned from past tasks\n{memory_context}"

        # ── Check for handoff context from another agent ──
        handoff = self.comms.get_handoff_context(agent_type)
        if handoff:
            context = f"{context}\n\n{handoff}" if context else handoff

        # Emit agent start event + update monitor
        event_bus.emit("agent_started", {
            "agent": agent_type,
            "task": task[:200],
            "attempt": attempt,
        })
        self.monitor.on_started(agent_type, task[:200], attempt)

        self.logger.info(f"🚀 Deploying {agent_type} agent (attempt {attempt}): {task[:100]}")

        # Create and run the agent
        agent = agent_class(
            llm_client=self.llm_client,
            model=self.heavy_model,
            max_steps=40,
            phone=self.phone,
        )

        result = agent.run(task, context=context)

        # ── Post-task: record in self-improvement engine ──
        escalation_history = self.escalation.failure_log[-3:] if attempt > 1 else []
        self.self_improve.record_task_outcome(
            agent_name=agent_type,
            task=task,
            result=result,
            escalation_history=escalation_history,
        )

        # ── If success, create handoff context for potential follow-up agents ──
        if result.get("success"):
            self.comms.send(
                from_agent=agent_type,
                to_agent="brain",
                content=result.get("content", "")[:500],
                msg_type="result",
            )

        # Emit agent completion event + update monitor
        event_bus.emit("agent_completed", {
            "agent": agent_type,
            "success": result.get("success", False),
            "steps": result.get("steps", 0),
            "stuck": result.get("stuck", False),
        })
        self.monitor.on_completed(agent_type, result.get("success", False), result.get("steps", 0))

        # ── Handle stuck agents — escalation chain ──
        if result.get("stuck") and attempt <= 3:
            stuck_reason = result.get("stuck_reason", result.get("content", "Unknown"))
            self.logger.warning(f"⚠️ {agent_type} agent stuck: {stuck_reason[:200]}")

            # Ask escalation manager what to do
            escalation = self.escalation.handle_stuck(
                agent_name=agent_type,
                task=task,
                stuck_reason=stuck_reason,
                attempt=attempt,
            )

            event_bus.emit("agent_escalated", {
                "agent": agent_type,
                "strategy": escalation["strategy"],
                "message": escalation["message"][:200],
            })
            self.monitor.on_escalated(agent_type)

            self.logger.info(f"🔄 Escalation strategy: {escalation['strategy']} — {escalation['message'][:100]}")

            strategy = escalation["strategy"]

            if strategy == "retry":
                # Retry same agent with guidance
                return self._deploy_agent(
                    agent_type=escalation["agent"],
                    task=task,
                    context=escalation["context"],
                    attempt=attempt + 1,
                )

            elif strategy == "reroute":
                # Try a different agent
                return self._deploy_agent(
                    agent_type=escalation["agent"],
                    task=task,
                    context=escalation["context"],
                    attempt=attempt + 1,
                )

            elif strategy == "decompose":
                # Retry with decomposition guidance
                return self._deploy_agent(
                    agent_type=escalation["agent"],
                    task=task,
                    context=escalation["context"],
                    attempt=attempt + 1,
                )

            elif strategy == "ask_user":
                # Send iMessage and wait for user response
                self.sender.send(escalation["message"])
                event_bus.emit("imessage_sent", {"message": escalation["message"]})

                reply = self.reader.wait_for_reply(timeout=300)
                if reply.get("success"):
                    user_response = reply["content"]
                    event_bus.emit("imessage_received", {"message": user_response})

                    if user_response.lower().strip() in ("skip", "cancel", "stop", "nevermind"):
                        return {"success": False, "content": "Task skipped by user."}

                    # Retry with user's guidance
                    return self._deploy_agent(
                        agent_type=agent_type,
                        task=task,
                        context=f"User's guidance: {user_response}",
                        attempt=1,  # Reset attempts with user guidance
                    )
                else:
                    return {"success": False, "content": f"Agent stuck and user didn't respond. {stuck_reason}"}

        # Clear failure log on success
        if result.get("success"):
            self.escalation.clear_log()

        return result
