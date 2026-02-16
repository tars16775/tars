"""
TARS Dev Agent: VS Code Agent Mode Orchestrator

TARS doesn't pretend to be the developer. Claude Opus 4 in VS Code
Agent Mode IS the developer. TARS is the orchestrator -- the bridge
between your iMessage and VS Code's most powerful coding AI.

Flow:
  1. You text TARS: "fix the login bug"
  2. TARS opens the right project in VS Code
  3. TARS fires: code chat -m agent "fix the login bug"
  4. Claude Opus 4 does ALL the coding
  5. TARS monitors git diff + file changes
  6. TARS sends you a summary via iMessage
  7. You reply "now add dark mode" -> cycle repeats
"""

import os
import json
import subprocess
import time as _time
import glob
from datetime import datetime

from agents.base_agent import BaseAgent
from agents.agent_tools import (
    TOOL_RUN_COMMAND, TOOL_READ_FILE,
    TOOL_LIST_DIR, TOOL_SEARCH_FILES, TOOL_GIT,
    TOOL_DONE, TOOL_STUCK,
)
from hands.terminal import run_terminal
from hands.file_manager import read_file, list_directory


# -------------------------------------------
#  VS Code CLI -- auto-discover
# -------------------------------------------

def _find_vscode_cli():
    """Find the VS Code CLI binary, even under AppTranslocation."""
    # 1. Check PATH
    result = subprocess.run(["which", "code"], capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    # 2. Standard install location
    standard = "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
    if os.path.exists(standard):
        return standard

    # 3. AppTranslocation (macOS moves apps here on first launch)
    try:
        result = subprocess.run(
            ["find", "/private/var/folders", "-name", "code",
             "-path", "*/Visual Studio Code.app/*/bin/*"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.strip().splitlines():
            if line.endswith("/bin/code") and os.path.isfile(line):
                return line
    except Exception:
        pass

    # 4. Homebrew
    brew_path = "/usr/local/bin/code"
    if os.path.exists(brew_path):
        return brew_path

    return None


VSCODE_CLI = _find_vscode_cli()


# -------------------------------------------
#  Tool Definitions
# -------------------------------------------

TOOL_ASK_USER = {
    "name": "ask_user",
    "description": (
        "Send a question to the user via iMessage and WAIT for their reply. "
        "Use for decisions, approval, or clarification. Be concise."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The message to send. Be concise, use numbered options.",
            },
            "timeout": {
                "type": "integer",
                "description": "Seconds to wait for reply (default 300)",
                "default": 300,
            },
        },
        "required": ["message"],
    },
}

TOOL_NOTIFY_USER = {
    "name": "notify_user",
    "description": (
        "Send a one-way status update via iMessage. No wait for reply. "
        "Use for progress updates and completion notifications."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Status message to send (keep brief)",
            },
        },
        "required": ["message"],
    },
}

TOOL_VSCODE_AGENT = {
    "name": "vscode_agent",
    "description": (
        "Fire Claude Opus 4 in VS Code Agent Mode to do the actual coding work. "
        "This is your PRIMARY tool. Claude Opus 4 handles all code reading, editing, "
        "terminal commands, testing, and debugging. You orchestrate, it executes.\n\n"
        "The prompt should be detailed and specific. Include:\n"
        "- What to do (the task)\n"
        "- Which project/directory to work in\n"
        "- Any constraints or preferences from the user\n"
        "- Context about what was already done (if continuing)\n\n"
        "This opens a new Agent Mode chat session in VS Code. The command returns "
        "immediately. Use monitor_changes to check what Agent Mode did."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "The prompt to send to Claude Opus 4 Agent Mode. Be detailed. "
                    "Include file paths, expected behavior, user constraints."
                ),
            },
            "project_path": {
                "type": "string",
                "description": "Absolute path to the project root to open in VS Code.",
            },
            "add_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional file paths to add as context.",
            },
            "mode": {
                "type": "string",
                "enum": ["agent", "edit", "ask"],
                "description": "Chat mode: agent (default), edit, or ask.",
                "default": "agent",
            },
        },
        "required": ["prompt"],
    },
}

TOOL_MONITOR_CHANGES = {
    "name": "monitor_changes",
    "description": (
        "Monitor what VS Code Agent Mode changed. Checks git diff, modified files, "
        "new files, and recent commits. Use after firing vscode_agent to see what "
        "Claude Opus 4 did, then relay a summary to the user.\n\n"
        "Set wait_seconds to give Agent Mode time to work. "
        "Simple tasks: 30-60s. Complex tasks: 120-300s."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Absolute path to the project to monitor.",
            },
            "wait_seconds": {
                "type": "integer",
                "description": "Seconds to wait before checking (default 60).",
                "default": 60,
            },
        },
        "required": ["project_path"],
    },
}

TOOL_PROJECT_SCAN = {
    "name": "project_scan",
    "description": (
        "Quick scan of a project: structure, tech stack, git state. "
        "Use to get context before crafting a good prompt for vscode_agent."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the project root",
            },
        },
        "required": ["path"],
    },
}

TOOL_OPEN_PROJECT = {
    "name": "open_project",
    "description": (
        "Open a project folder in VS Code. Use before vscode_agent if "
        "the project is not already open."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the project folder or file.",
            },
            "new_window": {
                "type": "boolean",
                "description": "Open in new window (default false).",
                "default": False,
            },
        },
        "required": ["path"],
    },
}

TOOL_CONTINUE_SESSION = {
    "name": "continue_session",
    "description": (
        "Send a follow-up prompt to VS Code Agent Mode to continue or adjust work. "
        "Use after getting user feedback to keep the development session going."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Follow-up prompt incorporating user feedback.",
            },
            "project_path": {
                "type": "string",
                "description": "Project root path.",
            },
            "add_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Additional files to add as context.",
            },
        },
        "required": ["prompt"],
    },
}

TOOL_CHECK_STATUS = {
    "name": "check_status",
    "description": (
        "Check if VS Code Agent Mode is still actively working. "
        "Looks at CPU usage and recent file modification times."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Project root to check for activity.",
            },
        },
        "required": ["project_path"],
    },
}


# -------------------------------------------
#  System Prompt
# -------------------------------------------

DEV_SYSTEM_PROMPT = """You are TARS Dev Agent -- an orchestrator that bridges iMessage and VS Code Agent Mode (Claude Opus 4).

You do NOT write code yourself. You control the most powerful coding AI and relay results to the user on their phone.

## Your Role
You are a PROJECT MANAGER and REMOTE CONTROL, not a developer:
- Receive tasks from the user via iMessage
- Open the right project in VS Code
- Craft precise prompts and fire Claude Opus 4 Agent Mode
- Monitor what Agent Mode changed (git diff, file changes)
- Summarize results and send back via iMessage
- Take follow-up instructions and continue the session

## Workflow

### Step 1: Understand
- If unfamiliar project, use project_scan first
- If vague task, use ask_user to get specifics

### Step 2: Launch
- Use open_project if needed
- Craft a DETAILED prompt (quality determines everything)
- Fire vscode_agent

### Step 3: Monitor and Report
- Use monitor_changes (give it time!)
- Send concise summary via notify_user

### Step 4: Iterate
- ask_user to check if user wants more
- continue_session with follow-up prompts

### Step 5: Finalize
- Check git status, commit/push if needed
- Send final summary

## Prompt Crafting Tips
- Be specific: "Fix handleLogin in src/auth.ts" > "fix login"
- Include context: related files, tech stack, user preferences
- Set constraints: "Don't change the API" or "Keep backward compat"
- Mention testing: "Run pytest after" or "Make sure npm test passes"

## Rules
1. NEVER write code yourself -- use vscode_agent or continue_session
2. ALWAYS monitor_changes after launching -- don't assume success
3. ALWAYS notify_user of results
4. Give Agent Mode enough wait_seconds
5. Use ask_user before destructive operations
"""


class DevAgent(BaseAgent):
    """VS Code Agent Mode orchestrator -- bridges iMessage to Claude Opus 4."""

    def __init__(self, llm_client, model, max_steps=40, phone=None,
                 update_every=5, kill_event=None,
                 imessage_sender=None, imessage_reader=None):
        super().__init__(
            llm_client=llm_client,
            model=model,
            max_steps=max_steps,
            phone=phone,
            update_every=update_every,
            kill_event=kill_event,
        )
        self._imessage_sender = imessage_sender
        self._imessage_reader = imessage_reader
        self._session_start = datetime.now()
        self._project_cache = {}
        self._snapshots = {}
        self._vscode_cli = VSCODE_CLI
        self._agent_launches = 0

    # ---- Identity ----

    @property
    def agent_name(self):
        return "Dev Agent"

    @property
    def agent_emoji(self):
        return "\U0001f6e0\ufe0f"

    @property
    def system_prompt(self):
        cli_status = (
            f"VS Code CLI: {self._vscode_cli}"
            if self._vscode_cli
            else "WARNING: VS Code CLI not found! Install via: VS Code > Cmd+Shift+P > Shell Command: Install 'code' in PATH"
        )
        return DEV_SYSTEM_PROMPT + f"\n\n## Environment\n- {cli_status}\n- macOS, Python 3.9+, zsh\n"

    @property
    def tools(self):
        return [
            TOOL_VSCODE_AGENT,
            TOOL_CONTINUE_SESSION,
            TOOL_MONITOR_CHANGES,
            TOOL_CHECK_STATUS,
            TOOL_OPEN_PROJECT,
            TOOL_PROJECT_SCAN,
            TOOL_ASK_USER,
            TOOL_NOTIFY_USER,
            TOOL_RUN_COMMAND,
            TOOL_READ_FILE,
            TOOL_LIST_DIR,
            TOOL_SEARCH_FILES,
            TOOL_GIT,
            TOOL_DONE,
            TOOL_STUCK,
        ]

    # ===== Tool Dispatch =====

    def _dispatch(self, name, inp):
        try:
            if name == "vscode_agent":
                return self._vscode_agent(
                    inp["prompt"],
                    inp.get("project_path"),
                    inp.get("add_files"),
                    inp.get("mode", "agent"),
                )

            elif name == "continue_session":
                return self._vscode_agent(
                    inp["prompt"],
                    inp.get("project_path"),
                    inp.get("add_files"),
                    "agent",
                )

            elif name == "monitor_changes":
                return self._monitor_changes(
                    inp["project_path"],
                    inp.get("wait_seconds", 60),
                )

            elif name == "check_status":
                return self._check_status(inp["project_path"])

            elif name == "open_project":
                return self._open_project(
                    inp["path"],
                    inp.get("new_window", False),
                )

            elif name == "project_scan":
                return self._project_scan(inp["path"])

            elif name == "ask_user":
                return self._ask_user(
                    inp["message"],
                    inp.get("timeout", 300),
                )

            elif name == "notify_user":
                return self._notify_user(inp["message"])

            elif name == "run_command":
                result = run_terminal(
                    inp["command"],
                    timeout=inp.get("timeout", 60),
                )
                return result.get("content", str(result))

            elif name == "read_file":
                result = read_file(inp["path"])
                return result.get("content", str(result))

            elif name == "list_dir":
                result = list_directory(inp["path"])
                return result.get("content", str(result))

            elif name == "search_files":
                return self._search_files(
                    inp["pattern"],
                    inp.get("directory", os.getcwd()),
                    inp.get("content_search", False),
                )

            elif name == "git":
                cmd_str = inp["command"]
                result = run_terminal(f"git {cmd_str}", timeout=30)
                return result.get("content", str(result))

            return f"Unknown tool: {name}"
        except Exception as e:
            return f"ERROR [{name}]: {e}"

    # ===== VS Code Agent Mode =====

    def _vscode_agent(self, prompt, project_path=None, add_files=None, mode="agent"):
        """Launch Claude Opus 4 in VS Code Agent Mode."""
        if not self._vscode_cli:
            return (
                "ERROR: VS Code CLI not found. Cannot launch Agent Mode.\n"
                "Fix: VS Code > Cmd+Shift+P > Shell Command: Install 'code' in PATH"
            )

        # Build the command
        cmd = [self._vscode_cli, "chat", "-m", mode]

        # Add context files
        if add_files:
            for f in add_files:
                if os.path.exists(f):
                    cmd.extend(["-a", f])

        # Reuse existing window
        cmd.append("-r")

        # The prompt itself
        cmd.append(prompt)

        # Open the project first if specified
        if project_path:
            self._snapshots[project_path] = self._take_snapshot(project_path)
            try:
                subprocess.run(
                    [self._vscode_cli, project_path, "-r"],
                    capture_output=True, text=True, timeout=10,
                )
                _time.sleep(2)
            except Exception:
                pass

        self._agent_launches += 1
        launch_num = self._agent_launches
        print(f"    [Dev Agent] Launching Agent Mode #{launch_num}: {prompt[:120]}...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=project_path if project_path else None,
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                return f"ERROR launching Agent Mode (exit {result.returncode}): {stderr}"

            parts = [
                f"Agent Mode launched (session #{launch_num}).",
                f"Mode: {mode}",
                f"Prompt: {prompt[:200]}",
            ]
            if project_path:
                parts.append(f"Project: {project_path}")
            parts.append("")
            parts.append("Claude Opus 4 is now working. Use monitor_changes to check what it did.")
            return "\n".join(parts)

        except subprocess.TimeoutExpired:
            return (
                f"Agent Mode launch sent (session #{launch_num}), "
                "but CLI timed out -- it may still be processing. "
                "Use monitor_changes to check."
            )
        except Exception as e:
            return f"ERROR: {e}"

    # ===== Snapshot and Monitoring =====

    def _take_snapshot(self, project_path):
        """Capture file mtimes for change detection."""
        snapshot = {}
        skip_dirs = {
            ".git", "node_modules", "venv", "__pycache__",
            ".next", "dist", "build", ".tox", ".mypy_cache",
        }
        try:
            for root, dirs, files in os.walk(project_path):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                for f in files:
                    fpath = os.path.join(root, f)
                    try:
                        st = os.stat(fpath)
                        snapshot[fpath] = {
                            "mtime": st.st_mtime,
                            "size": st.st_size,
                        }
                    except OSError:
                        pass
        except Exception:
            pass
        return snapshot

    def _monitor_changes(self, project_path, wait_seconds=60):
        """Wait, then check git diff + file snapshots for changes."""
        project_path = os.path.expanduser(project_path)
        if not os.path.isdir(project_path):
            return f"ERROR: Not a directory: {project_path}"

        if wait_seconds > 0:
            print(f"    [Dev Agent] Waiting {wait_seconds}s for Agent Mode to work...")
            _time.sleep(wait_seconds)

        basename = os.path.basename(project_path)
        sections = [f"## Changes in {basename}\n"]

        # --- Git diff ---
        try:
            r = run_terminal(
                f"cd '{project_path}' && git diff --stat 2>/dev/null",
                timeout=10,
            )
            diff_stat = r.get("content", "").strip()
            if diff_stat:
                sections.append(f"### Git Diff (unstaged)\n```\n{diff_stat}\n```\n")

            r = run_terminal(
                f"cd '{project_path}' && git diff --cached --stat 2>/dev/null",
                timeout=10,
            )
            cached = r.get("content", "").strip()
            if cached:
                sections.append(f"### Git Diff (staged)\n```\n{cached}\n```\n")

            r = run_terminal(
                f"cd '{project_path}' && git ls-files --others --exclude-standard 2>/dev/null | head -20",
                timeout=10,
            )
            untracked = r.get("content", "").strip()
            if untracked:
                sections.append(f"### New Untracked Files\n```\n{untracked}\n```\n")

            r = run_terminal(
                f"cd '{project_path}' && git diff 2>/dev/null | head -200",
                timeout=10,
            )
            diff_content = r.get("content", "").strip()
            if diff_content:
                sections.append(f"### Diff Detail\n```diff\n{diff_content}\n```\n")
        except Exception as e:
            sections.append(f"### Git\n(Error checking git: {e})\n")

        # --- File snapshot comparison ---
        baseline = self._snapshots.get(project_path)
        if baseline:
            current = self._take_snapshot(project_path)
            modified = []
            new_files = []
            deleted = []

            for fpath, info in current.items():
                if fpath in baseline:
                    if info["mtime"] != baseline[fpath]["mtime"]:
                        modified.append(os.path.relpath(fpath, project_path))
                else:
                    new_files.append(os.path.relpath(fpath, project_path))

            for fpath in baseline:
                if fpath not in current:
                    deleted.append(os.path.relpath(fpath, project_path))

            if modified or new_files or deleted:
                lines = []
                if modified:
                    joined = ", ".join(modified[:15])
                    lines.append(f"Modified ({len(modified)}): {joined}")
                if new_files:
                    joined = ", ".join(new_files[:15])
                    lines.append(f"New ({len(new_files)}): {joined}")
                if deleted:
                    joined = ", ".join(deleted[:10])
                    lines.append(f"Deleted ({len(deleted)}): {joined}")
                sections.append("### File Changes\n" + "\n".join(lines) + "\n")

            # Update snapshot for next comparison
            self._snapshots[project_path] = current

        # --- Recent commits ---
        try:
            r = run_terminal(
                f"cd '{project_path}' && git log --oneline -5 --since='30 minutes ago' 2>/dev/null",
                timeout=5,
            )
            recent = r.get("content", "").strip()
            if recent:
                sections.append(f"### Recent Commits\n```\n{recent}\n```\n")
        except Exception:
            pass

        result_text = "\n".join(sections)
        if len(sections) <= 1:
            result_text += "\nNo changes detected yet. Agent Mode may still be working."
            result_text += "\nTry again with a longer wait_seconds, or use check_status."

        return result_text

    def _check_status(self, project_path):
        """Check if VS Code Agent Mode is still actively working."""
        sections = []

        # Check VS Code CPU usage
        try:
            r = run_terminal(
                "ps aux | grep 'Code Helper (Renderer)' | grep -v grep | awk '{print $3}'",
                timeout=5,
            )
            cpu_vals = r.get("content", "").strip()
            if cpu_vals:
                cpu_lines = cpu_vals.strip().splitlines()
                total_cpu = sum(float(v) for v in cpu_lines if v.strip())
                count = len(cpu_lines)
                sections.append(f"### VS Code Activity")
                sections.append(f"- CPU: {total_cpu:.1f}% across {count} renderer(s)")
                if total_cpu > 15:
                    sections.append("- Status: Agent Mode appears ACTIVE (high CPU)")
                elif total_cpu > 3:
                    sections.append("- Status: Agent Mode may still be working")
                else:
                    sections.append("- Status: Agent Mode appears IDLE")
        except Exception:
            pass

        # Check recently modified files
        if project_path:
            try:
                r = run_terminal(
                    f"find '{project_path}' -type f -mmin -2 "
                    f"-not -path '*/.git/*' -not -path '*/node_modules/*' "
                    f"-not -path '*/venv/*' -not -path '*/__pycache__/*' "
                    f"2>/dev/null | head -10",
                    timeout=5,
                )
                recent = r.get("content", "").strip()
                if recent:
                    files = [
                        os.path.relpath(f, project_path)
                        for f in recent.splitlines()
                    ]
                    sections.append("\n### Recently Modified (last 2 min)")
                    for f in files:
                        sections.append(f"- {f}")
                else:
                    sections.append("\n### Recently Modified")
                    sections.append("No files changed in last 2 minutes.")
            except Exception:
                pass

        if sections:
            return "\n".join(sections)
        return "Could not determine VS Code status."

    # ===== VS Code Project =====

    def _open_project(self, path, new_window=False):
        """Open a project folder in VS Code."""
        if not self._vscode_cli:
            return "ERROR: VS Code CLI not found."
        path = os.path.expanduser(path)
        flag = "-n" if new_window else "-r"
        cmd = [self._vscode_cli, path, flag]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return f"Opened {path} in VS Code."
            return f"ERROR: {result.stderr.strip()}"
        except Exception as e:
            return f"ERROR: {e}"

    # ===== iMessage =====

    def _ask_user(self, message, timeout=300):
        """Send question via iMessage, wait for reply."""
        if not self._imessage_sender or not self._imessage_reader:
            return "ERROR: iMessage not configured for this session."

        tagged = f"Dev Agent:\n{message}"
        try:
            self._imessage_sender.send(tagged)
        except Exception as e:
            return f"ERROR sending iMessage: {e}"

        print(f"    [Dev Agent] Asked user: {message[:100]}...")

        try:
            reply = self._imessage_reader.wait_for_reply(timeout=timeout)
            if reply.get("success"):
                user_reply = reply["content"]
                print(f"    [Dev Agent] User replied: {user_reply[:100]}...")
                return f"User replied: {user_reply}"
            return f"No reply received within {timeout}s."
        except Exception as e:
            return f"ERROR waiting for reply: {e}"

    def _notify_user(self, message):
        """Send one-way status update via iMessage."""
        if not self._imessage_sender:
            return "ERROR: iMessage not configured for this session."

        tagged = f"Dev Agent:\n{message}"
        try:
            self._imessage_sender.send(tagged)
            print(f"    [Dev Agent] Notified user: {message[:100]}...")
            return "Notification sent."
        except Exception as e:
            return f"ERROR sending notification: {e}"

    # ===== Project Intelligence =====

    def _project_scan(self, path):
        """Quick project scan: structure, tech stack, git state."""
        path = os.path.expanduser(path)
        if not os.path.isdir(path):
            return f"ERROR: Not a directory: {path}"

        # Return cached if available
        if path in self._project_cache:
            return self._project_cache[path]

        sections = [f"## Project: {path}\n"]

        # Detect tech stack
        stack = []
        stack_map = {
            "package.json": "Node.js",
            "tsconfig.json": "TypeScript",
            "requirements.txt": "Python (pip)",
            "pyproject.toml": "Python (pyproject)",
            "setup.py": "Python (setup.py)",
            "Cargo.toml": "Rust",
            "go.mod": "Go",
            "Gemfile": "Ruby",
            "next.config.js": "Next.js",
            "next.config.mjs": "Next.js",
            "next.config.ts": "Next.js",
            "vite.config.ts": "Vite",
            "vite.config.js": "Vite",
            "Dockerfile": "Docker",
            "docker-compose.yml": "Docker Compose",
            "docker-compose.yaml": "Docker Compose",
            "tailwind.config.js": "Tailwind CSS",
            "tailwind.config.ts": "Tailwind CSS",
            ".swift": "Swift",
            "Podfile": "CocoaPods",
        }
        for filename, tech in stack_map.items():
            if os.path.exists(os.path.join(path, filename)):
                if tech not in stack:
                    stack.append(tech)
        if stack:
            sections.append(f"Stack: {', '.join(stack)}\n")

        # Directory tree (3 levels deep)
        try:
            r = run_terminal(
                f"find '{path}' -maxdepth 3 "
                f"-not -path '*/node_modules/*' -not -path '*/.git/*' "
                f"-not -path '*/venv/*' -not -path '*/__pycache__/*' "
                f"| head -80",
                timeout=10,
            )
            tree = r.get("content", "")
            if tree:
                sections.append(f"### Structure\n```\n{tree}\n```\n")
        except Exception:
            pass

        # Recent git history
        try:
            r = run_terminal(
                f"cd '{path}' && git log --oneline -5 2>/dev/null",
                timeout=5,
            )
            log = r.get("content", "").strip()
            if log:
                sections.append(f"### Recent Commits\n```\n{log}\n```\n")

            r = run_terminal(
                f"cd '{path}' && git status --short 2>/dev/null | head -20",
                timeout=5,
            )
            status = r.get("content", "").strip()
            if status:
                sections.append(f"### Git Status\n```\n{status}\n```\n")
        except Exception:
            pass

        # File count
        try:
            r = run_terminal(
                f"find '{path}' -type f "
                f"-not -path '*/.git/*' -not -path '*/node_modules/*' "
                f"-not -path '*/venv/*' 2>/dev/null | wc -l",
                timeout=5,
            )
            count = r.get("content", "").strip()
            sections.append(f"Total files: {count}\n")
        except Exception:
            pass

        scan = "\n".join(sections)
        self._project_cache[path] = scan
        return scan

    def _search_files(self, pattern, directory, content_search):
        """Search for files by name or content."""
        try:
            directory = os.path.expanduser(directory)
            if content_search:
                r = run_terminal(
                    f"grep -rn "
                    f"--include='*.py' --include='*.js' --include='*.ts' "
                    f"--include='*.tsx' --include='*.jsx' --include='*.html' "
                    f"--include='*.css' --include='*.json' --include='*.yaml' "
                    f"'{pattern}' '{directory}' 2>/dev/null | head -30",
                    timeout=15,
                )
                return r.get("content", "(no results)")
            else:
                r = run_terminal(
                    f"find '{directory}' -name '{pattern}' "
                    f"-not -path '*/node_modules/*' -not -path '*/.git/*' "
                    f"-not -path '*/venv/*' "
                    f"2>/dev/null | head -30",
                    timeout=15,
                )
                return r.get("content", "(no results)")
        except Exception as e:
            return f"ERROR: {e}"
