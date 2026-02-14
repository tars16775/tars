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
            self.imessage_sender.send("🛑 TARS stopped. Send a new task when ready.")
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

        if initial_task:
            # Start with a task from command line
            print(f"  📋 Initial task: {initial_task}\n")
            self._process_task(initial_task)
        else:
            # No task — announce on iMessage and wait
            self.imessage_sender.send("🤖 TARS is online and ready. What should I work on?")
            event_bus.emit("imessage_sent", {"message": "🤖 TARS is online and ready. What should I work on?"})
            print("  📱 Sent startup message. Waiting for instructions...\n")

        # Main loop — keep working forever
        while self.running:
            try:
                # Wait for a new task via iMessage
                print("  ⏳ Waiting for next task via iMessage...")
                reply = self.imessage_reader.wait_for_reply(timeout=3600)  # 1 hour timeout

                if reply.get("success"):
                    task = reply["content"]
                    event_bus.emit("imessage_received", {"message": task})

                    # Check kill switch
                    if any(kw.lower() in task.lower() for kw in self.kill_words):
                        print(f"  🛑 Kill command received: {task}")
                        self.imessage_sender.send("🛑 TARS stopped. Send a new task when ready.")
                        event_bus.emit("kill_switch", {"source": "imessage"})
                        continue

                    # Process the task
                    self._process_task(task)
                else:
                    # Timed out — send a check-in
                    self.imessage_sender.send("💤 TARS is idle. Send me a task whenever you're ready.")

            except KeyboardInterrupt:
                self._shutdown()
            except Exception as e:
                self.logger.error(f"Loop error: {e}")
                self.imessage_sender.send(f"⚠️ TARS encountered an error: {e}\nI'll keep running.")
                time.sleep(5)

    def _process_task(self, task):
        """Process a single task through the Claude brain."""
        print(f"\n  {'═' * 50}")
        print(f"  📋 Task: {task}")
        print(f"  {'═' * 50}\n")

        self.logger.info(f"New task: {task}")
        event_bus.emit("task_received", {"task": task, "source": "agent"})
        event_bus.emit("status_change", {"status": "working", "label": "WORKING"})

        # Update context
        self.memory.update_context(
            f"# Current Task\n\n{task}\n\nStarted: {datetime.now().isoformat()}\n"
        )

        # Send task to Claude brain
        response = self.brain.think(task)

        # Log the result
        self.logger.info(f"Task completed. Response: {response[:200]}")

        event_bus.emit("status_change", {"status": "online", "label": "ONLINE"})

        print(f"\n  {'─' * 50}")
        print(f"  ✅ Task cycle complete")
        print(f"  {'─' * 50}\n")


# ─── Entry Point ─────────────────────────────────────

if __name__ == "__main__":
    tars = TARS()

    # Check if a task was passed as an argument
    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
        tars.run(initial_task=task)
    else:
        tars.run()
