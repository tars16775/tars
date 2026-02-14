"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Inter-Agent Communication Hub                    ║
╠══════════════════════════════════════════════════════════════╣
║  Message passing between agents via the orchestrator brain.  ║
║  Brain is the central hub — no direct agent-to-agent comms.  ║
╚══════════════════════════════════════════════════════════════╝
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AgentMessage:
    """A message passed between agents via the brain."""
    from_agent: str
    to_agent: str
    content: str
    msg_type: str = "info"       # info, request, result, handoff
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


class AgentComms:
    """Central communication hub for inter-agent messaging.
    
    All communication flows through the brain (orchestrator):
      Agent A → Brain → Agent B
    
    This tracks handoff context so agents can build on each
    other's work without losing information.
    """

    def __init__(self):
        self._messages: List[AgentMessage] = []
        self._handoff_context: Dict[str, str] = {}  # agent → context from prev agent

    def send(self, from_agent: str, to_agent: str, content: str,
             msg_type: str = "info", metadata: Dict = None) -> AgentMessage:
        """Record a message from one agent to another."""
        msg = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            msg_type=msg_type,
            metadata=metadata or {},
        )
        self._messages.append(msg)
        return msg

    def handoff(self, from_agent: str, to_agent: str, context: str,
                task: str = "") -> str:
        """Create a handoff context when one agent passes work to another.
        
        Returns the formatted context string to inject into the receiving agent.
        """
        handoff_text = (
            f"=== HANDOFF FROM {from_agent.upper()} AGENT ===\n"
            f"Previous agent ({from_agent}) worked on this task and provides context:\n"
            f"{context}\n"
            f"{'Task for you: ' + task if task else ''}\n"
            f"=== END HANDOFF ==="
        )

        self._handoff_context[to_agent] = handoff_text

        self.send(
            from_agent=from_agent,
            to_agent=to_agent,
            content=context,
            msg_type="handoff",
            metadata={"task": task},
        )

        return handoff_text

    def get_handoff_context(self, agent_name: str) -> Optional[str]:
        """Get any handoff context waiting for an agent, then clear it."""
        ctx = self._handoff_context.pop(agent_name, None)
        return ctx

    def get_messages(self, agent: str = None, msg_type: str = None,
                     limit: int = 20) -> List[AgentMessage]:
        """Get recent messages, optionally filtered."""
        msgs = self._messages
        if agent:
            msgs = [m for m in msgs if m.from_agent == agent or m.to_agent == agent]
        if msg_type:
            msgs = [m for m in msgs if m.msg_type == msg_type]
        return msgs[-limit:]

    def get_conversation_log(self) -> str:
        """Get a formatted log of all agent communications."""
        if not self._messages:
            return "No inter-agent communications yet."

        lines = ["=== Agent Communication Log ==="]
        for msg in self._messages[-30:]:  # Last 30 messages
            ts = time.strftime("%H:%M:%S", time.localtime(msg.timestamp))
            lines.append(f"[{ts}] {msg.from_agent} → {msg.to_agent} ({msg.msg_type}): {msg.content[:200]}")
        return "\n".join(lines)

    def clear(self):
        """Clear all messages and handoff context."""
        self._messages.clear()
        self._handoff_context.clear()


# Global singleton
agent_comms = AgentComms()
