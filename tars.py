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
    """Load configuration from config.yaml."""
    config_path = os.path.join(BASE_DIR, "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


class TARS:
    def __init__(self):
        print(BANNER)

        # Load config
        self.config = load_config()
        print("  ⚙️  Config loaded")

        # Validate API key
        llm_cfg = self.config["llm"]
        api_key = llm_cfg["api_key"]
        provider = llm_cfg["provider"]
        if not api_key or api_key.startswith("YOUR_"):
            provider_urls = {
                "groq": "https://console.groq.com/keys",
                "together": "https://api.together.xyz/settings/api-keys",
                "anthropic": "https://console.anthropic.com/settings/keys",
                "openrouter": "https://openrouter.ai/keys",
                "openai": "https://platform.openai.com/api-keys",
            }
            url = provider_urls.get(provider, "your provider's dashboard")
            print(f"\n  ❌ ERROR: Set your {provider} API key in config.yaml")
            print(f"  → Open config.yaml and set llm.api_key")
            print(f"  → Get a key at: {url}\n")
            sys.exit(1)
        print(f"  🤖 LLM provider: {provider}")

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

        self.executor = ToolExecutor(
            self.config, self.imessage_sender, self.imessage_reader, self.memory, self.logger
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

        self.running = True
        self.kill_words = self.config["safety"]["kill_words"]
        self._task_lock = threading.Lock()  # Prevent concurrent task processing

        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, *args):
        """Graceful shutdown."""
        print("\n\n  🛑 TARS shutting down...")

        # Print session summary from self-improvement engine
        if hasattr(self.executor, 'self_improve'):
            summary = self.executor.self_improve.get_session_summary()
            if summary:
                print(f"\n{summary}\n")

        self.running = False
        self.memory.update_context(
            f"# TARS — Last Session\n\nShutdown at {datetime.now().isoformat()}\n"
        )
        sys.exit(0)

    def _check_kill_switch(self):
        """Check if user sent a kill command via iMessage."""
        killed, msg = self.imessage_reader.check_for_kill(self.kill_words)
        if killed:
            print(f"\n  🛑 Kill switch activated: '{msg}'")
            return True
        return False

    def run(self, initial_task=None):
        """Main agent loop."""
        print(f"\n  {'─' * 50}")
        print(f"  🟢 TARS is online — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  {'─' * 50}\n")

        event_bus.emit("status_change", {"status": "online", "label": "ONLINE"})

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

                    # Check kill switch
                    if any(kw.lower() in task.lower() for kw in self.kill_words):
                        print(f"  🛑 Kill command received: {task}")
                        event_bus.emit("kill_switch", {"source": "imessage"})
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
        Thread-safe: only one task can run at a time.
        """
        if not self._task_lock.acquire(blocking=False):
            print(f"  ⚠️ Task already running, queueing: {task[:80]}")
            self._task_lock.acquire()  # Block until current task finishes
        
        try:
            print(f"\n  {'═' * 50}")
            print(f"  📨 Message: {task}")
            print(f"  {'═' * 50}\n")

            self.logger.info(f"New message: {task}")
            event_bus.emit("task_received", {"task": task, "source": "agent"})
            event_bus.emit("status_change", {"status": "working", "label": "WORKING"})

            # Reset deployment tracker (fresh agent budget) but NOT conversation
            self.executor.reset_task_tracker()

            # Send to brain — it classifies and handles everything
            response = self.brain.think(task)

            # Log the result
            self.logger.info(f"Cycle complete. Response: {response[:200]}")

            event_bus.emit("status_change", {"status": "online", "label": "ONLINE"})

            print(f"\n  {'─' * 50}")
            print(f"  ✅ Cycle complete")
            print(f"  {'─' * 50}\n")
        finally:
            self._task_lock.release()


# ─── Entry Point ─────────────────────────────────────

if __name__ == "__main__":
    tars = TARS()

    # Check if a task was passed as an argument
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        tars.run(initial_task=task)
    else:
        tars.run()
