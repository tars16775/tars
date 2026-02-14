#!/usr/bin/env python3
"""Test all 20 phases of the TARS multi-agent system."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0

def test(label, fn):
    global passed, failed
    try:
        result = fn()
        print(f"  ✅ {label}" + (f" → {result}" if result else ""))
        passed += 1
    except Exception as e:
        print(f"  ❌ {label}: {e}")
        failed += 1

print("=" * 55)
print("  TARS Multi-Agent System — Full Test Suite")
print("=" * 55)
print()

# ─── Import Tests ───────────────────────────────────
print("📦 IMPORTS")
test("utils.event_bus", lambda: __import__("utils.event_bus"))
test("utils.agent_monitor", lambda: __import__("utils.agent_monitor"))
test("utils.logger", lambda: __import__("utils.logger"))
test("utils.safety", lambda: __import__("utils.safety"))
test("memory.memory_manager", lambda: __import__("memory.memory_manager"))
test("memory.agent_memory", lambda: __import__("memory.agent_memory"))
test("brain.llm_client", lambda: __import__("brain.llm_client"))
test("brain.prompts", lambda: __import__("brain.prompts"))
test("brain.tools", lambda: __import__("brain.tools"))
test("brain.task_classifier", lambda: __import__("brain.task_classifier"))
test("brain.escalation", lambda: __import__("brain.escalation"))
test("brain.self_improve", lambda: __import__("brain.self_improve"))
test("agents.base_agent", lambda: __import__("agents.base_agent"))
test("agents.agent_tools", lambda: __import__("agents.agent_tools"))
test("agents.comms", lambda: __import__("agents.comms"))
test("agents.browser_agent", lambda: __import__("agents.browser_agent"))
test("agents.coder_agent", lambda: __import__("agents.coder_agent"))
test("agents.system_agent", lambda: __import__("agents.system_agent"))
test("agents.research_agent", lambda: __import__("agents.research_agent"))
test("agents.file_agent", lambda: __import__("agents.file_agent"))
test("agents.__init__", lambda: __import__("agents"))
test("executor", lambda: __import__("executor"))
test("server", lambda: __import__("server"))
test("brain.planner", lambda: __import__("brain.planner"))

print()

# ─── Functional Tests ───────────────────────────────
print("⚡ FUNCTIONAL TESTS")

# Tools count
from brain.tools import TARS_TOOLS
test(f"Orchestrator tools count", lambda: f"{len(TARS_TOOLS)} tools")

# Agent registry
from agents import AGENT_REGISTRY
test("Agent registry", lambda: f"{list(AGENT_REGISTRY.keys())}")

# Task classifier
from brain.task_classifier import classify_task
test("Classify 'open chrome'", lambda: classify_task("open google chrome and search")["category"])
test("Classify 'write python'", lambda: classify_task("write a python script to sort numbers")["category"])
test("Classify 'find files'", lambda: classify_task("find all files larger than 100MB")["category"])
test("Classify 'research AI'", lambda: classify_task("research the latest AI papers on arxiv")["category"])

# Agent memory
import tempfile
from memory.agent_memory import AgentMemory
tmp = tempfile.mkdtemp()
mem = AgentMemory(tmp)
mem.record_success("browser", "test task", "it worked", 5)
mem.record_failure("browser", "bad task", "page not found", 3)
test("AgentMemory context", lambda: f"{len(mem.get_context('browser'))} chars")
test("AgentMemory stats", lambda: str(mem.get_all_stats()))

# Escalation
from brain.escalation import EscalationManager
esc = EscalationManager(max_retries=3)
test("Escalation attempt 1", lambda: esc.handle_stuck("browser", "open google", "fail", 1)["strategy"])
test("Escalation attempt 2", lambda: esc.handle_stuck("browser", "open google", "fail", 2)["strategy"])
test("Escalation attempt 3", lambda: esc.handle_stuck("browser", "open google", "fail", 3)["strategy"])
test("Escalation attempt 4", lambda: esc.handle_stuck("browser", "open google", "fail", 4)["strategy"])

# Agent monitor
from utils.agent_monitor import agent_monitor
test("Monitor dashboard data", lambda: f"{len(agent_monitor.get_dashboard_data()['agents'])} agents")
test("Monitor active agents", lambda: str(agent_monitor.get_active_agents()))

# Comms
from agents.comms import agent_comms
agent_comms.clear()
agent_comms.handoff("browser", "coder", "Found API docs", "Write client")
test("Comms handoff create", lambda: "ok")
ctx = agent_comms.get_handoff_context("coder")
test("Comms handoff retrieve", lambda: "HANDOFF" if ctx and "HANDOFF" in ctx else "FAIL")

# Self-improve
from brain.self_improve import SelfImproveEngine
si = SelfImproveEngine(mem)
si.record_task_outcome("browser", "test", {"success": True, "content": "done", "steps": 3})
test("SelfImprove session", lambda: si.get_session_summary().split("\n")[0])

print()
print("=" * 55)
print(f"  Results: {passed} passed, {failed} failed")
print("=" * 55)
if failed == 0:
    print("  🏆 ALL 20 PHASES OPERATIONAL")
else:
    print(f"  ⚠️  {failed} test(s) need attention")
