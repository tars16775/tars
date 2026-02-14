"""
╔══════════════════════════════════════════╗
║       TARS — Tool Executor               ║
╚══════════════════════════════════════════╝

Bridges LLM tool_use calls to actual
system actions. Routes each tool to its handler.
"""

from hands.mac_control import open_app, type_text, key_press, click, get_frontmost_app, take_screenshot
from hands.terminal import run_terminal
from hands.file_manager import read_file, write_file, move_file, delete_file, list_directory
from hands.browser import act_google as browser_google
from hands.browser_agent import BrowserAgent
from brain.llm_client import LLMClient
from utils.safety import is_destructive, is_path_allowed


class ToolExecutor:
    def __init__(self, config, imessage_sender, imessage_reader, memory_manager, logger):
        self.config = config
        self.sender = imessage_sender
        self.reader = imessage_reader
        self.memory = memory_manager
        self.logger = logger
        self.confirm_destructive = config["safety"]["confirm_destructive"]
        self.allowed_paths = config["safety"]["allowed_paths"]

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

        # ─── Terminal ────────────────────────────
        if tool_name == "run_terminal":
            cmd = inp["command"]
            # Safety check for destructive commands
            if self.confirm_destructive and is_destructive(cmd):
                self.logger.warning(f"⚠️ Destructive command detected: {cmd}")
                self.sender.send(f"⚠️ TARS wants to run a destructive command:\n\n{cmd}\n\nReply YES to confirm or NO to cancel.")
                reply = self.reader.wait_for_reply(timeout=120)
                if not reply.get("success") or "yes" not in reply["content"].lower():
                    return {"success": False, "content": "Command cancelled by user."}
            return run_terminal(cmd, timeout=inp.get("timeout", 60))

        # ─── Mac Control ─────────────────────────
        elif tool_name == "open_app":
            return open_app(inp["app_name"])
        elif tool_name == "type_text":
            return type_text(inp["text"])
        elif tool_name == "key_press":
            return key_press(inp["keys"])
        elif tool_name == "click":
            return click(inp["x"], inp["y"], inp.get("double_click", False))
        elif tool_name == "get_frontmost_app":
            return get_frontmost_app()
        elif tool_name == "take_screenshot":
            return take_screenshot()

        # ─── File Operations ─────────────────────
        elif tool_name == "read_file":
            return read_file(inp["file_path"])
        elif tool_name == "write_file":
            return write_file(inp["file_path"], inp["content"])
        elif tool_name == "move_file":
            return move_file(inp["source"], inp["destination"])
        elif tool_name == "delete_file":
            # Safety check
            if self.confirm_destructive:
                path = inp["file_path"]
                self.sender.send(f"⚠️ TARS wants to delete:\n{path}\n\nReply YES to confirm.")
                reply = self.reader.wait_for_reply(timeout=120)
                if not reply.get("success") or "yes" not in reply["content"].lower():
                    return {"success": False, "content": "Delete cancelled by user."}
            return delete_file(inp["file_path"], inp.get("recursive", False))
        elif tool_name == "list_directory":
            return list_directory(inp["dir_path"])

        # ─── Browser (Agentic) ────────────────────
        elif tool_name == "web_task":
            # Launch the autonomous browser agent with iMessage progress updates
            llm_cfg = self.config["llm"]
            llm_client = LLMClient(
                provider=llm_cfg["provider"],
                api_key=llm_cfg["api_key"],
                base_url=llm_cfg.get("base_url"),
            )
            agent = BrowserAgent(
                llm_client=llm_client,
                model=llm_cfg["heavy_model"],
                phone=self.config["imessage"]["owner_phone"],
            )
            result = agent.run(inp["task"])
            return result
        elif tool_name == "web_search":
            text = browser_google(inp["query"])
            return {"success": True, "content": text}

        # ─── iMessage ────────────────────────────
        elif tool_name == "send_imessage":
            return self.sender.send(inp["message"])
        elif tool_name == "wait_for_reply":
            return self.reader.wait_for_reply(timeout=inp.get("timeout", 300))

        # ─── Memory ──────────────────────────────
        elif tool_name == "save_memory":
            return self.memory.save(inp["category"], inp["key"], inp["value"])
        elif tool_name == "recall_memory":
            return self.memory.recall(inp["query"])

        else:
            return {"success": False, "error": True, "content": f"Unknown tool: {tool_name}"}
