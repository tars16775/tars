#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Full Live System Test                            ║
╠══════════════════════════════════════════════════════════════╣
║  Tests the ENTIRE multi-agent pipeline end-to-end:           ║
║    1. Import chain                                           ║
║    2. LLM connectivity (Groq)                                ║
║    3. Brain orchestrator (streaming)                          ║
║    4. Agent deployment (Coder Agent — safest to test)        ║
║    5. Escalation engine                                      ║
║    6. Agent memory + self-improve                            ║
║    7. Monitor + dashboard data                               ║
║    8. Full TARS boot sequence                                ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

passed = 0
failed = 0
results = []

def test(label):
    """Decorator for test functions."""
    def decorator(fn):
        def wrapper():
            global passed, failed
            print(f"\n  ⏳ {label}...")
            try:
                result = fn()
                print(f"  ✅ {label}" + (f"\n     → {result}" if result else ""))
                passed += 1
                results.append(("✅", label))
            except Exception as e:
                print(f"  ❌ {label}")
                print(f"     → {e}")
                traceback.print_exc()
                failed += 1
                results.append(("❌", label))
        wrapper.label = label
        return wrapper
    return decorator


# ═══════════════════════════════════════════════
#  Test Suite
# ═══════════════════════════════════════════════

@test("1. Full import chain (24 modules)")
def test_imports():
    from utils.event_bus import event_bus
    from utils.agent_monitor import agent_monitor
    from utils.logger import setup_logger
    from utils.safety import is_destructive
    from memory.memory_manager import MemoryManager
    from memory.agent_memory import AgentMemory
    from brain.llm_client import LLMClient
    from brain.prompts import TARS_SYSTEM_PROMPT
    from brain.tools import TARS_TOOLS
    from brain.task_classifier import classify_task
    from brain.escalation import EscalationManager
    from brain.self_improve import SelfImproveEngine
    from agents.base_agent import BaseAgent
    from agents.agent_tools import TOOL_DONE, TOOL_STUCK
    from agents.comms import agent_comms
    from agents.browser_agent import BrowserAgent
    from agents.coder_agent import CoderAgent
    from agents.system_agent import SystemAgent
    from agents.research_agent import ResearchAgent
    from agents.file_agent import FileAgent
    from agents import AGENT_REGISTRY
    from executor import ToolExecutor
    from server import TARSServer
    from brain.planner import TARSBrain
    return f"24/24 modules OK, {len(TARS_TOOLS)} brain tools, {len(AGENT_REGISTRY)} agents"


@test("2. Config loading")
def test_config():
    import yaml
    with open(os.path.join(BASE_DIR, "config.yaml")) as f:
        config = yaml.safe_load(f)
    provider = config["llm"]["provider"]
    model = config["llm"]["heavy_model"]
    key = config["llm"]["api_key"][:10] + "..."
    return f"Provider: {provider}, Model: {model}, Key: {key}"


@test("3. LLM client creation (Groq)")
def test_llm_client():
    import yaml
    from brain.llm_client import LLMClient
    with open(os.path.join(BASE_DIR, "config.yaml")) as f:
        config = yaml.safe_load(f)
    llm_cfg = config["llm"]
    client = LLMClient(
        provider=llm_cfg["provider"],
        api_key=llm_cfg["api_key"],
        base_url=llm_cfg.get("base_url"),
    )
    assert client._mode == "openai", f"Expected openai mode, got {client._mode}"
    return f"Mode: {client._mode}, Provider: {llm_cfg['provider']}"


@test("4. LLM non-streaming call (agent mode)")
def test_llm_create():
    import yaml
    from brain.llm_client import LLMClient
    with open(os.path.join(BASE_DIR, "config.yaml")) as f:
        config = yaml.safe_load(f)
    llm_cfg = config["llm"]
    client = LLMClient(
        provider=llm_cfg["provider"],
        api_key=llm_cfg["api_key"],
        base_url=llm_cfg.get("base_url"),
    )
    
    # Simple test: ask it to use a tool
    response = client.create(
        model=llm_cfg["heavy_model"],
        max_tokens=200,
        system="You are a test bot. Always respond with the done tool.",
        tools=[{
            "name": "done",
            "description": "Signal you are done.",
            "input_schema": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"]
            }
        }],
        messages=[{"role": "user", "content": "Say hello."}],
    )
    
    assert response.content, "No content blocks returned"
    types = [b.type for b in response.content]
    return f"Blocks: {types}, Stop: {response.stop_reason}, Tokens: {response.usage.input_tokens}in/{response.usage.output_tokens}out"


@test("5. LLM streaming call (brain mode)")
def test_llm_stream():
    import yaml
    from brain.llm_client import LLMClient
    with open(os.path.join(BASE_DIR, "config.yaml")) as f:
        config = yaml.safe_load(f)
    llm_cfg = config["llm"]
    client = LLMClient(
        provider=llm_cfg["provider"],
        api_key=llm_cfg["api_key"],
        base_url=llm_cfg.get("base_url"),
    )
    
    chunks = []
    with client.stream(
        model=llm_cfg["fast_model"],
        max_tokens=100,
        system="You are TARS. Reply in one sentence.",
        tools=[],
        messages=[{"role": "user", "content": "What are you?"}],
    ) as stream:
        for event in stream:
            if event.type == "content_block_delta" and hasattr(event.delta, "text"):
                chunks.append(event.delta.text)
        response = stream.get_final_message()
    
    full_text = "".join(chunks)
    assert len(full_text) > 5, f"Stream too short: '{full_text}'"
    assert response.stop_reason == "end_turn"
    return f"Streamed {len(chunks)} chunks, {len(full_text)} chars: '{full_text[:80]}...'"


@test("6. Task classifier (rule-based)")
def test_classifier():
    from brain.task_classifier import classify_task
    tests = {
        "go to google.com and search for pizza": "browser",
        "write a python flask app": "coder",
        "open spotify and play music": "system",
        "find all png files over 10MB": "file",
    }
    results = []
    for task, expected in tests.items():
        r = classify_task(task)
        actual = r["category"]
        status = "✓" if actual == expected else f"✗ got {actual}"
        results.append(f"{status} '{task[:30]}' → {actual}")
    return "\n     " + "\n     ".join(results)


@test("7. Escalation chain (4 strategies)")
def test_escalation():
    from brain.escalation import EscalationManager
    esc = EscalationManager(max_retries=3)
    strategies = []
    for attempt in range(1, 5):
        r = esc.handle_stuck("browser", "open google", "page failed to load", attempt)
        strategies.append(r["strategy"])
    assert strategies == ["retry", "reroute", "decompose", "ask_user"], f"Got: {strategies}"
    return f"Strategies: {' → '.join(strategies)}"


@test("8. Agent memory (persist + recall)")
def test_agent_memory():
    import tempfile
    from memory.agent_memory import AgentMemory
    
    tmp = tempfile.mkdtemp()
    mem = AgentMemory(tmp)
    
    # Record some outcomes
    mem.record_success("coder", "write hello world", "wrote main.py", 3)
    mem.record_success("coder", "fix bug", "patched error", 5)
    mem.record_failure("coder", "deploy to AWS", "credentials missing", 8)
    
    # Get context
    ctx = mem.get_context("coder")
    assert "2/3 tasks succeeded" in ctx or "67%" in ctx, f"Stats wrong: {ctx}"
    assert "credentials missing" in ctx, "Failure pattern missing"
    
    # Stats
    stats = mem.get_all_stats()
    assert len(stats) > 0
    return f"Context: {len(ctx)} chars, Stats: {stats}"


@test("9. Agent monitor")
def test_monitor():
    from utils.agent_monitor import agent_monitor
    
    # Simulate agent lifecycle
    agent_monitor.on_started("coder", "write code", 1)
    assert agent_monitor.get_active_agents() == ["coder"]
    
    agent_monitor.on_step("coder", 5)
    status = agent_monitor.get_status("coder")
    assert status["step"] == 5
    
    agent_monitor.on_completed("coder", True, 8)
    assert agent_monitor.get_active_agents() == []
    
    dashboard = agent_monitor.get_dashboard_data()
    assert len(dashboard["agents"]) == 5
    
    agent_monitor.reset()
    return f"5 agents tracked, lifecycle OK"


@test("10. Inter-agent comms")
def test_comms():
    from agents.comms import AgentComms
    
    comms = AgentComms()
    comms.handoff("browser", "coder", "Found API at api.example.com/v2", "Build the client")
    
    # Coder should receive handoff context
    ctx = comms.get_handoff_context("coder")
    assert ctx and "HANDOFF" in ctx
    assert "api.example.com" in ctx
    
    # Should be cleared after retrieval
    ctx2 = comms.get_handoff_context("coder")
    assert ctx2 is None
    
    log = comms.get_conversation_log()
    assert "browser → coder" in log
    return "Handoff + retrieval + clearing OK"


@test("11. Self-improvement engine")
def test_self_improve():
    import tempfile
    from memory.agent_memory import AgentMemory
    from brain.self_improve import SelfImproveEngine
    
    tmp = tempfile.mkdtemp()
    mem = AgentMemory(tmp)
    si = SelfImproveEngine(mem)
    
    si.record_task_outcome("browser", "search google", {"success": True, "content": "found results", "steps": 4})
    si.record_task_outcome("coder", "write script", {"success": False, "content": "syntax error", "steps": 10, "stuck": True, "stuck_reason": "SyntaxError in main.py"})
    
    summary = si.get_session_summary()
    assert "2 total" in summary or "Tasks: 2" in summary
    assert "1 ✅" in summary
    
    stats = si.get_all_agent_stats()
    assert len(stats) >= 2
    return f"Session: 2 tasks tracked, stats for {len(stats)} agents"


@test("12. LIVE: Coder Agent (write + verify a file)")
def test_coder_agent_live():
    """Actually deploy the Coder Agent to write a small file and verify it."""
    import yaml
    from brain.llm_client import LLMClient
    from agents.coder_agent import CoderAgent
    
    with open(os.path.join(BASE_DIR, "config.yaml")) as f:
        config = yaml.safe_load(f)
    llm_cfg = config["llm"]
    
    client = LLMClient(
        provider=llm_cfg["provider"],
        api_key=llm_cfg["api_key"],
        base_url=llm_cfg.get("base_url"),
    )
    
    # Clean up any previous test file
    test_file = os.path.join(BASE_DIR, "_test_agent_output.py")
    if os.path.exists(test_file):
        os.remove(test_file)
    
    agent = CoderAgent(
        llm_client=client,
        model=llm_cfg["heavy_model"],
        max_steps=10,
        phone=None,  # No iMessage for tests
    )
    
    result = agent.run(
        f"Write a Python file at {test_file} that contains a function called 'add' that takes two numbers and returns their sum. "
        f"After writing, read the file to verify it was written correctly. Then call done with a summary."
    )
    
    # Verify
    assert result["success"], f"Agent failed: {result.get('content', result.get('stuck_reason'))}"
    assert os.path.exists(test_file), "Test file was not created"
    
    with open(test_file) as f:
        content = f.read()
    assert "def add" in content, f"Function 'add' not found in file content: {content[:200]}"
    
    # Cleanup
    os.remove(test_file)
    
    return f"Success in {result['steps']} steps. File verified with 'def add'. Content: {content.strip()[:100]}"


@test("13. LIVE: File Agent (list + inspect)")
def test_file_agent_live():
    """Deploy the File Agent to list a directory."""
    import yaml
    from brain.llm_client import LLMClient
    from agents.file_agent import FileAgent
    
    with open(os.path.join(BASE_DIR, "config.yaml")) as f:
        config = yaml.safe_load(f)
    llm_cfg = config["llm"]
    
    client = LLMClient(
        provider=llm_cfg["provider"],
        api_key=llm_cfg["api_key"],
        base_url=llm_cfg.get("base_url"),
    )
    
    agent = FileAgent(
        llm_client=client,
        model=llm_cfg["heavy_model"],
        max_steps=8,
        phone=None,
    )
    
    result = agent.run(
        f"List the contents of the directory {BASE_DIR} and tell me how many .py files are in the root (not subdirectories). "
        f"Then call done with the count."
    )
    
    assert result["success"], f"Agent failed: {result.get('content', result.get('stuck_reason'))}"
    return f"Success in {result['steps']} steps: {result['content'][:120]}"


@test("14. LIVE: Full executor pipeline (deploy_coder_agent)")
def test_executor_pipeline():
    """Test the full executor → agent → memory → self_improve pipeline."""
    import yaml
    from executor import ToolExecutor
    from memory.memory_manager import MemoryManager
    from utils.logger import setup_logger
    
    with open(os.path.join(BASE_DIR, "config.yaml")) as f:
        config = yaml.safe_load(f)
    
    logger = setup_logger(config, BASE_DIR)
    memory = MemoryManager(config, BASE_DIR)
    
    # Create a minimal sender/reader that doesn't actually send iMessages
    class MockSender:
        def send(self, msg): return {"success": True, "content": "sent"}
    class MockReader:
        def wait_for_reply(self, timeout=300): return {"success": False, "content": "timeout"}
    
    executor = ToolExecutor(config, MockSender(), MockReader(), memory, logger)
    
    # Clean up
    test_file = os.path.join(BASE_DIR, "_test_executor_output.txt")
    if os.path.exists(test_file):
        os.remove(test_file)
    
    # Deploy via executor (same path the brain uses)
    result = executor.execute("deploy_coder_agent", {
        "task": f"Write a file at {test_file} containing the text 'TARS EXECUTOR TEST PASSED'. Then read it to verify. Call done."
    })
    
    assert result.get("success"), f"Executor failed: {result}"
    assert os.path.exists(test_file), "File not created by executor pipeline"
    
    with open(test_file) as f:
        content = f.read()
    assert "TARS EXECUTOR TEST PASSED" in content
    
    # Verify self-improvement recorded the outcome
    stats = executor.self_improve.get_session_summary()
    assert "1" in stats  # At least 1 task recorded
    
    # Cleanup
    os.remove(test_file)
    
    return f"Full pipeline OK. Result: {result['content'][:100]}"


# ═══════════════════════════════════════════════
#  Run All Tests
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print()
    print("  ═" * 30)
    print("  🧪 TARS MULTI-AGENT SYSTEM — FULL LIVE TEST")
    print("  ═" * 30)
    
    start = time.time()
    
    # Run all tests in order
    test_imports()
    test_config()
    test_llm_client()
    test_llm_create()
    test_llm_stream()
    test_classifier()
    test_escalation()
    test_agent_memory()
    test_monitor()
    test_comms()
    test_self_improve()
    test_coder_agent_live()
    test_file_agent_live()
    test_executor_pipeline()
    
    elapsed = time.time() - start
    
    print()
    print("  ═" * 30)
    print(f"  📊 RESULTS: {passed} passed, {failed} failed ({elapsed:.1f}s)")
    print("  ═" * 30)
    
    for emoji, label in results:
        print(f"  {emoji} {label}")
    
    print()
    if failed == 0:
        print("  🏆 ALL SYSTEMS OPERATIONAL — TARS IS READY")
    else:
        print(f"  ⚠️  {failed} test(s) need attention")
    print()
