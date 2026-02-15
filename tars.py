#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║                 ████████╗ █████╗ ██████╗ ███████╗        ║
║                 ╚══██╔══╝██╔══██╗██╔══██╗██╔════╝        ║
║                    ██║   ███████║██████╔╝███████╗        ║
║                    ██║   ██╔══██║██╔══██╗╚════██║        ║
║                    ██║   ██║  ██║██║  ██║███████║        ║
║                    ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝        ║
║                                                          ║
║          Autonomous Mac Agent — Your Workflow             ║
║                    Never Stops                           ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

Usage:
    python tars.py                    # Start TARS, waits for iMessage
    python tars.py "build a website"  # Start with a task
"""

import os
import sys
import yaml
import time
import queue
import signal
import threading
from datetime import datetime

# Set working directory to script location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from brain.planner import TARSBrain
from executor import ToolExecutor
from voice.imessage_send import IMessageSender
from voice.imessage_read import IMessageReader
from memory.memory_manager import MemoryManager
from memory.agent_memory import AgentMemory
from utils.logger import setup_logger
from utils.event_bus import event_bus
from utils.agent_monitor import agent_monitor
from server import TARSServer
from hands import mac_control as mac


# ─── Banner ──────────────────────────────────────────

BANNER = """
\033[36m
  ████████╗ █████╗ ██████╗ ███████╗
  ╚══██╔══╝██╔══██╗██╔══██╗██╔════╝
     ██║   ███████║██████╔╝███████╗
     ██║   ██╔══██║██╔══██╗╚════██║
     ██║   ██║  ██║██║  ██║███████║
     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝
\033[0m
  \033[90mAutonomous Mac Agent — v3.0 Multi-Agent\033[0m
  \033[90m"Humor: 75% — Honesty: 90%"\033[0m
  \033[90mDashboard: http://localhost:8420\033[0m
"""


def load_config():
    """Load configuration from config.yaml with env var overrides.
    
    API keys can be set via environment variables:
      TARS_BRAIN_API_KEY  →  brain_llm.api_key
      TARS_AGENT_API_KEY  →  agent_llm.api_key + llm.api_key
    """
    config_path = os.path.join(BASE_DIR, "config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # Env var overrides for API keys (so they never need to be in yaml)
    if os.environ.get("TARS_BRAIN_API_KEY"):
        config.setdefault("brain_llm", {})["api_key"] = os.environ["TARS_BRAIN_API_KEY"]
    if os.environ.get("TARS_AGENT_API_KEY"):
        config.setdefault("agent_llm", {})["api_key"] = os.environ["TARS_AGENT_API_KEY"]
        config.setdefault("llm", {})["api_key"] = os.environ["TARS_AGENT_API_KEY"]
    
    return config


class TARS:
    def __init__(self):
        print(BANNER)

        # Load config
        self.config = load_config()
        print("  ⚙️  Config loaded")

        # Validate API keys — both brain and agent
        provider_urls = {
            "groq": "https://console.groq.com/keys",
            "together": "https://api.together.xyz/settings/api-keys",
            "anthropic": "https://console.anthropic.com/settings/keys",
            "openrouter": "https://openrouter.ai/keys",
            "openai": "https://platform.openai.com/api-keys",
            "gemini": "https://aistudio.google.com/apikey",
        }

        # Validate brain LLM key
        brain_cfg = self.config.get("brain_llm", {})
        brain_key = brain_cfg.get("api_key", "")
        brain_provider = brain_cfg.get("provider", "")
        if brain_key and not brain_key.startswith("YOUR_"):
            print(f"  🧠 Brain LLM: {brain_provider}/{brain_cfg.get('model', '?')}")
        elif brain_provider:
            url = provider_urls.get(brain_provider, "your provider's dashboard")
            print(f"\n  ❌ ERROR: Brain API key missing or invalid")
            print(f"  → Set brain_llm.api_key in config.yaml")
            print(f"  → Or: export TARS_BRAIN_API_KEY=your_key")
            print(f"  → Get a key at: {url}\n")
            sys.exit(1)

        # Validate agent LLM key  
        llm_cfg = self.config["llm"]
        api_key = llm_cfg["api_key"]
        provider = llm_cfg["provider"]
        if not api_key or api_key.startswith("YOUR_"):
            url = provider_urls.get(provider, "your provider's dashboard")
            print(f"\n  ❌ ERROR: Set your {provider} API key in config.yaml")
            print(f"  → Open config.yaml and set llm.api_key")
            print(f"  → Or: export TARS_AGENT_API_KEY=your_key")
            print(f"  → Get a key at: {url}\n")
            sys.exit(1)
        print(f"  🤖 Agent LLM: {provider}")

        # Initialize components
        self.logger = setup_logger(self.config, BASE_DIR)
        print("  📝 Logger ready")

        self.memory = MemoryManager(self.config, BASE_DIR)
        print("  🧠 Memory loaded")

        self.agent_memory = AgentMemory(BASE_DIR)
        print("  🧬 Agent memory loaded")

        self.imessage_sender = IMessageSender(self.config)
        self.imessage_reader = IMessageReader(self.config)
        print("  📱 iMessage bridge ready")

        # Must init before executor/brain so they can reference these
        self.running = True
        self.kill_words = self.config["safety"]["kill_words"]
        self._kill_event = threading.Event()  # Shared kill signal — stops running agents
        self._task_queue = queue.Queue()  # Thread-safe task queue
        self._progress_interval = self.config.get("imessage", {}).get("progress_interval", 30)  # Seconds between progress updates

        self.executor = ToolExecutor(
            self.config, self.imessage_sender, self.imessage_reader, self.memory, self.logger,
            kill_event=self._kill_event,
        )
        print("  🔧 Orchestrator executor ready")
        print(f"     ├─ 🌐 Browser Agent")
        print(f"     ├─ 💻 Coder Agent")
        print(f"     ├─ ⚙️  System Agent")
        print(f"     ├─ 🔍 Research Agent")
        print(f"     └─ 📁 File Agent")

        self.brain = TARSBrain(self.config, self.executor, self.memory)
        print("  🤖 Orchestrator brain online")

        self.monitor = agent_monitor
        print("  📊 Agent monitor active")

        # Start dashboard server
        self.server = TARSServer(memory_manager=self.memory, tars_instance=self)
        self.server.start()
        print("  🖥️  Dashboard live at \033[36mhttp://localhost:8420\033[0m")

        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, *args):
        """Graceful shutdown — stops agents, drains queue, then exits."""
        print("\n\n  🛑 TARS shutting down...")

        # Signal all running agents to stop
        self._kill_event.set()
        self.running = False

        # Wait for current task to finish (up to 10s)
        try:
            self._task_queue.join()  # blocks until task_done() called
        except Exception:
            pass

        # Print session summary from self-improvement engine
        if hasattr(self.executor, 'self_improve'):
            summary = self.executor.self_improve.get_session_summary()
            if summary:
                print(f"\n{summary}\n")

        self.memory.update_context(
            f"# TARS — Last Session\n\nShutdown at {datetime.now().isoformat()}\n"
        )
        sys.exit(0)

    def run(self, initial_task=None):
        """Main agent loop."""
        print(f"\n  {'─' * 50}")
        print(f"  🟢 TARS is online — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  {'─' * 50}\n")

        event_bus.emit("status_change", {"status": "online", "label": "ONLINE"})

        # ── Environment snapshot on startup ──
        print("  🌍 Taking environment snapshot...")
        try:
            snapshot = mac.get_environment_snapshot()
            if snapshot.get("success"):
                self._last_snapshot = snapshot.get("snapshot", {})
                self.memory.save("context", "startup_environment", snapshot.get("content", ""))
                apps = snapshot.get("snapshot", {}).get("running_apps", [])
                print(f"  ✅ Snapshot: {len(apps)} apps running, volume {snapshot.get('snapshot', {}).get('volume', '?')}%")
            else:
                self._last_snapshot = {}
                print("  ⚠️ Snapshot partial — continuing")
        except Exception as e:
            self._last_snapshot = {}
            print(f"  ⚠️ Snapshot skipped: {e}")

        # Start task worker thread (processes queue serially)
        worker = threading.Thread(target=self._task_worker, daemon=True)
        worker.start()

        # Dashboard URL (don't auto-open — it interferes with Chrome browser tools)
        print(f"  🌐 Open dashboard: http://localhost:8420\n")

        # Notify owner that TARS is online and ready
        try:
            self.imessage_sender.send("✅ TARS is online and all systems are functional. Ready for commands.")
            print("  📱 Startup notification sent via iMessage")
        except Exception as e:
            print(f"  ⚠️ Could not send startup iMessage: {e}")

        if initial_task:
            # Start with a task from command line
            print(f"  📋 Initial task: {initial_task}\n")
            self._process_task(initial_task)
        else:
            # No task — wait for messages (conversation-ready)
            print("  📱 Listening for messages...\n")

        # Main loop — keep working forever
        while self.running:
            try:
                # Wait for a new message via iMessage
                conv_msgs = self.brain._message_count
                conv_ctx = len(self.brain.conversation_history)
                print(f"  ⏳ Waiting for message... (conversation: {conv_msgs} msgs, {conv_ctx} ctx entries)")
                reply = self.imessage_reader.wait_for_reply(timeout=3600)  # 1 hour timeout

                if reply.get("success"):
                    task = reply["content"]
                    event_bus.emit("imessage_received", {"message": task})

                    # Check kill switch — stops all running agents
                    if any(kw.lower() in task.lower() for kw in self.kill_words):
                        print(f"  🛑 Kill command received: {task}")
                        self._kill_event.set()  # Signal all running agents to stop
                        event_bus.emit("kill_switch", {"source": "imessage"})
                        try:
                            self.imessage_sender.send("🛑 Kill switch activated — all agents stopped.")
                        except Exception:
                            pass
                        # Reset kill event after a beat so new tasks can run
                        time.sleep(1)
                        self._kill_event.clear()
                        continue

                    # Process the message (brain classifies: chat vs task)
                    self._process_task(task)
                else:
                    # Timed out — just keep waiting silently
                    print("  💤 Still waiting...")

            except KeyboardInterrupt:
                self._shutdown()
            except Exception as e:
                self.logger.error(f"Loop error: {e}")
                print(f"  ⚠️ Error: {e} — continuing...")
                time.sleep(5)

    def _process_task(self, task):
        """
        Process a message through the TARS brain.
        
        v4: The brain handles classification (chat vs task) internally.
        We DON'T reset conversation history — TARS remembers the flow.
        We only reset the deployment budget so each message gets fresh agents.
        Thread-safe: queued via self._task_queue so messages are never lost.
        """
        # Put task on queue — the worker processes them in order
        self._task_queue.put(task)

    def _task_worker(self):
        """Background worker that processes tasks from the queue, one at a time."""
        while self.running:
            try:
                task = self._task_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                print(f"\n  {'═' * 50}")
                print(f"  📨 Message: {task}")
                print(f"  {'═' * 50}\n")

                self.logger.info(f"New message: {task}")
                event_bus.emit("task_received", {"task": task, "source": "agent"})
                event_bus.emit("status_change", {"status": "working", "label": "WORKING"})

                # Reset deployment tracker (fresh agent budget) but NOT conversation
                self.executor.reset_task_tracker()

                # ── Streaming progress: debounced updates to iMessage ──
                progress_collector = _ProgressCollector(
                    sender=self.imessage_sender,
                    interval=self._progress_interval,
                )
                progress_collector.start()

                # Send to brain — wrapped in try/finally so progress
                # collector is ALWAYS cleaned up, even on crash
                try:
                    response = self.brain.think(task)
                finally:
                    progress_collector.stop()

                # Log the result
                self.logger.info(f"Cycle complete. Response: {response[:200]}")

                # ── Safety net: if brain returned an error, notify user ──
                if response and (response.startswith("❌") or response.startswith("⚠️")):
                    self.logger.warning(f"Brain returned error, notifying user: {response[:200]}")
                    try:
                        # Extract useful info from the error
                        if "leaked" in response.lower() or "PERMISSION_DENIED" in response:
                            self.imessage_sender.send("❌ API key issue — my brain API key needs to be replaced. Let me know when you've updated config.yaml and I'll retry.")
                        elif "rate limit" in response.lower() or "429" in response:
                            self.imessage_sender.send("⏳ Hit a rate limit. Give me a minute and send your request again.")
                        elif "Failed to call a function" in response:
                            self.imessage_sender.send("⚠️ Had a formatting hiccup with my response. Can you repeat your request? I'll get it right this time.")
                        else:
                            self.imessage_sender.send(f"⚠️ Ran into an issue: {response[:300]}")
                    except Exception:
                        pass  # Don't crash the loop trying to send error notification

                event_bus.emit("status_change", {"status": "online", "label": "ONLINE"})

                print(f"\n  {'─' * 50}")
                print(f"  ✅ Cycle complete")
                print(f"  {'─' * 50}\n")
            except Exception as e:
                self.logger.error(f"Task processing error: {e}")
                print(f"  ⚠️ Task error: {e}")
                # Notify user about crash so they're not left waiting
                try:
                    self.imessage_sender.send(f"⚠️ Something went wrong internally. Error: {str(e)[:200]}. Send your request again.")
                except Exception:
                    pass
                event_bus.emit("status_change", {"status": "online", "label": "ONLINE"})
            finally:
                self._task_queue.task_done()


class _ProgressCollector:
    """Collects agent/tool events and sends debounced progress updates to iMessage.
    
    Subscribes to event_bus for 'agent_started', 'agent_completed', 'tool_called'
    events. Every `interval` seconds, if there's new activity, sends a compact
    progress update via iMessage so the user knows what TARS is doing.
    """

    def __init__(self, sender, interval=30):
        self._sender = sender
        self._interval = interval
        self._events = []
        self._lock = threading.Lock()
        self._timer = None
        self._running = False

    def start(self):
        self._running = True
        event_bus.subscribe_sync("agent_started", self._on_event)
        event_bus.subscribe_sync("agent_completed", self._on_event)
        event_bus.subscribe_sync("tool_called", self._on_event)
        self._schedule_tick()

    def stop(self):
        self._running = False
        event_bus.unsubscribe_sync("agent_started", self._on_event)
        event_bus.unsubscribe_sync("agent_completed", self._on_event)
        event_bus.unsubscribe_sync("tool_called", self._on_event)
        if self._timer:
            self._timer.cancel()

    def _on_event(self, data):
        with self._lock:
            self._events.append(data)

    def _schedule_tick(self):
        if not self._running:
            return
        self._timer = threading.Timer(self._interval, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self):
        if not self._running:
            return
        with self._lock:
            events = self._events[:]
            self._events.clear()

        if events:
            # Build a compact progress summary
            parts = []
            for ev in events[-5:]:  # Last 5 events max
                if "agent" in ev and "task" in ev:
                    parts.append(f"🚀 {ev['agent']}: {ev['task'][:60]}")
                elif "agent" in ev and "success" in ev:
                    status = "✅" if ev["success"] else "❌"
                    parts.append(f"{status} {ev['agent']} done ({ev.get('steps', '?')} steps)")
                elif "tool_name" in ev:
                    parts.append(f"🔧 {ev['tool_name']}")

            if parts:
                msg = "⏳ Progress:\n" + "\n".join(parts)
                try:
                    self._sender.send(msg)
                except Exception:
                    pass

        self._schedule_tick()


# ─── Entry Point ─────────────────────────────────────

if __name__ == "__main__":
    tars = TARS()

    # Check if a task was passed as an argument
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        tars.run(initial_task=task)
    else:
        tars.run()
