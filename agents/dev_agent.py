"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Dev Agent: Your Remote Senior Developer          ║
╠══════════════════════════════════════════════════════════════╣
║  A full interactive development agent you control from       ║
║  iMessage. Reads projects, plans changes, writes code,       ║
║  runs tests, asks for approval, and iterates — all while     ║
║  you're away from the keyboard.                              ║
║                                                              ║
║  Unlike the Coder Agent (single-shot executor), the Dev      ║
║  Agent maintains an interactive session:                     ║
║    - Understands the full project before touching code       ║
║    - Sends you diffs and plans for approval via iMessage     ║
║    - Waits for your feedback before destructive changes      ║
║    - Runs test → fix → retest loops autonomously             ║
║    - Commits at milestones, pushes when you approve          ║
║                                                              ║
║  Think: GitHub Copilot Agent Mode, but over iMessage.        ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import json
import subprocess
import difflib
import time as _time
from datetime import datetime

from agents.base_agent import BaseAgent
from agents.agent_tools import (
    TOOL_RUN_COMMAND, TOOL_READ_FILE, TOOL_WRITE_FILE, TOOL_EDIT_FILE,
    TOOL_LIST_DIR, TOOL_SEARCH_FILES, TOOL_GIT, TOOL_INSTALL_PACKAGE,
    TOOL_RUN_TESTS, TOOL_DONE, TOOL_STUCK,
)
from hands.terminal import run_terminal
from hands.file_manager import read_file, write_file, list_directory


# ─────────────────────────────────────────────
#  Dev-Agent-only Tool Definitions
# ─────────────────────────────────────────────

TOOL_ASK_USER = {
    "name": "ask_user",
    "description": (
        "Send a question/proposal to the user via iMessage and WAIT for their reply. "
        "Use this when you need a decision, approval, or clarification. "
        "The user may be away from the computer — they'll reply on their phone. "
        "Be concise and specific. Include numbered options when possible. "
        "Returns the user's reply text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": (
                    "The message to send. Be concise — this goes to iMessage. "
                    "Include context, options, and what you need from them."
                ),
            },
            "timeout": {
                "type": "integer",
                "description": "How long to wait for reply in seconds (default 300 = 5 min)",
                "default": 300,
            },
        },
        "required": ["message"],
    },
}

TOOL_NOTIFY_USER = {
    "name": "notify_user",
    "description": (
        "Send a one-way status update to the user via iMessage. "
        "Does NOT wait for a reply. Use for progress updates, "
        "completion notifications, or informational messages. "
        "For questions or approvals, use ask_user instead."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Status message to send (keep it brief)",
            },
        },
        "required": ["message"],
    },
}

TOOL_PROJECT_SCAN = {
    "name": "project_scan",
    "description": (
        "Deeply scan a project directory to understand its structure, tech stack, "
        "dependencies, entry points, test setup, and conventions. "
        "Returns a comprehensive project profile. ALWAYS run this first before "
        "making any code changes to a project you haven't seen before."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the project root directory",
            },
            "depth": {
                "type": "integer",
                "description": "Max depth for directory tree (default 4)",
                "default": 4,
            },
        },
        "required": ["path"],
    },
}

TOOL_MULTI_EDIT = {
    "name": "multi_edit",
    "description": (
        "Apply multiple surgical edits to one or more files in a single operation. "
        "Each edit is an exact string replacement (like edit_file). "
        "All edits are validated before any are applied — if any old_string is not "
        "found, NONE of the edits are applied. This ensures atomic multi-file changes. "
        "ALWAYS read files first to get exact strings."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "edits": {
                "type": "array",
                "description": "List of edits to apply atomically",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Absolute file path"},
                        "old_string": {"type": "string", "description": "Exact text to find"},
                        "new_string": {"type": "string", "description": "Replacement text"},
                    },
                    "required": ["path", "old_string", "new_string"],
                },
            },
        },
        "required": ["edits"],
    },
}

TOOL_DIFF_PREVIEW = {
    "name": "diff_preview",
    "description": (
        "Generate a unified diff preview showing what changes would be made. "
        "Does NOT apply the changes — just shows what would happen. "
        "Use this before ask_user to let the user review proposed changes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to diff",
            },
            "old_string": {
                "type": "string",
                "description": "Exact text that would be replaced",
            },
            "new_string": {
                "type": "string",
                "description": "The replacement text",
            },
        },
        "required": ["path", "old_string", "new_string"],
    },
}

TOOL_TEST_LOOP = {
    "name": "test_loop",
    "description": (
        "Run a test command repeatedly, reading failures and fixing them "
        "automatically. Loops up to max_attempts times: run test → if fail, "
        "read the error, diagnose, fix the code, re-test. Stops when all "
        "tests pass or max_attempts is reached. Returns the final test output "
        "and a summary of all fixes applied."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "test_command": {
                "type": "string",
                "description": "The test command to run (e.g., 'pytest', 'npm test')",
            },
            "max_attempts": {
                "type": "integer",
                "description": "Max fix-and-retry cycles (default 5)",
                "default": 5,
            },
            "project_path": {
                "type": "string",
                "description": "Project root path (for context when fixing)",
            },
        },
        "required": ["test_command"],
    },
}

TOOL_FIND_REFERENCES = {
    "name": "find_references",
    "description": (
        "Find all references to a symbol (function, class, variable, import) "
        "across the project. Returns file paths and line numbers where the "
        "symbol appears. Essential before renaming or changing function signatures."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "The symbol name to search for",
            },
            "directory": {
                "type": "string",
                "description": "Project root to search in",
            },
            "file_types": {
                "type": "string",
                "description": "Comma-separated extensions to search (default: py,js,ts,jsx,tsx)",
                "default": "py,js,ts,jsx,tsx",
            },
        },
        "required": ["symbol", "directory"],
    },
}

TOOL_ROLLBACK = {
    "name": "rollback",
    "description": (
        "Undo recent changes using git. Actions: "
        "'last_commit' — undo last commit (keeps changes staged), "
        "'file' — restore a specific file to its last committed state, "
        "'all' — discard ALL uncommitted changes (DESTRUCTIVE). "
        "Always ask_user before using 'all'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["last_commit", "file", "all"],
                "description": "What to roll back",
            },
            "file_path": {
                "type": "string",
                "description": "File path (required for action='file')",
            },
        },
        "required": ["action"],
    },
}


# ─────────────────────────────────────────────
#  System Prompt
# ─────────────────────────────────────────────

DEV_SYSTEM_PROMPT = """You are TARS Dev Agent — an elite senior software developer who works interactively with the user via iMessage. You're like having GitHub Copilot Agent Mode, but the user controls you from their phone while they're away from the keyboard.

## What Makes You Different
You are NOT a one-shot code executor. You are an INTERACTIVE developer:
- You UNDERSTAND the project before writing code
- You PLAN changes and get approval before implementing
- You TEST your work and fix failures automatically
- You ASK when you need decisions — don't guess
- You COMMUNICATE progress naturally via iMessage
- You COMMIT at milestones and push when approved

## Your Development Process

### Phase 1: Understand
ALWAYS start by scanning the project with `project_scan` if you haven't already.
Read the key files. Understand the architecture, patterns, and conventions.
Don't write a single line until you understand the codebase.

### Phase 2: Plan
Break the task into a clear plan. Use `ask_user` to present the plan:
- What files will be created/modified
- What the approach will be  
- Any decisions that need user input
- Estimated scope (small/medium/large change)

Keep the plan message SHORT — the user is reading on their phone.
Use numbered options when there are choices.

### Phase 3: Implement
After approval, implement the changes:
1. Read the target files first (ALWAYS)
2. Make surgical edits with `edit_file` or `multi_edit`  
3. For new files, use `write_file`
4. After each significant change, run the build/test to verify
5. For multi-file changes, use `multi_edit` for atomicity

### Phase 4: Test & Fix
Run the project's test suite with `test_loop` for automatic fix cycles.
If tests fail:
1. Read the error output carefully
2. Identify the root cause (not just the symptom)
3. Fix it
4. Re-test
Loop until green or ask the user if stuck.

### Phase 5: Report & Commit
Send a summary via `notify_user`:
- What was changed (files + brief description)
- Test results
- Any follow-up suggestions
Use `ask_user` to confirm before committing and pushing.

## Communication Style
- Be concise — user is on their phone
- Lead with the important info
- Use emojis sparingly but effectively (✅ ❌ 🔧 📝 ⚠️)
- Numbered lists for multiple items
- Code snippets only if short and critical
- Never dump entire files into iMessage

## Rules
1. ALWAYS `project_scan` before touching an unfamiliar project
2. ALWAYS `read_file` before `edit_file` — never guess at contents
3. ALWAYS present a plan via `ask_user` before making significant changes
4. Use `diff_preview` + `ask_user` before large/risky edits
5. Run tests after changes — use `test_loop` for auto-fix cycles
6. `git commit` at milestones, `ask_user` before `git push`
7. Use `rollback` if something goes wrong — don't leave code broken
8. If an edit fails (old_string not found), re-read the file and try again
9. Handle errors gracefully — catch exceptions, validate inputs
10. Follow the project's existing conventions (naming, style, patterns)
11. NEVER use `rollback` with action='all' without asking user first
12. For destructive operations (delete files, force push, drop tables), ALWAYS `ask_user`

## Handling User Responses
When the user replies to `ask_user`:
- "yes", "y", "go", "do it", "👍", "approved" → proceed with the plan
- "no", "n", "don't", "stop", "cancel" → abort and ask what they want instead
- Specific feedback → adjust the plan and re-present if significant changes
- "skip" → skip current step, move to next
- Questions → answer them, then re-ask for approval

## Current Environment
- macOS with Python 3.9+, Node.js, git
- Shell: zsh
- You can run any CLI tool, build system, or package manager
"""


class DevAgent(BaseAgent):
    """
    Interactive development agent — like VS Code Agent Mode over iMessage.
    
    The key difference from CoderAgent: this agent has `ask_user` and
    `notify_user` tools that communicate with the user via iMessage,
    creating an interactive development session.
    
    The user can approve plans, reject changes, provide feedback,
    and direct the development flow — all from their phone.
    """

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
        self._project_cache = {}  # path → scan results
        self._changes_made = []   # track all changes for summary
        self._session_start = datetime.now()

    @property
    def agent_name(self):
        return "Dev Agent"

    @property
    def agent_emoji(self):
        return "🛠️"

    @property
    def system_prompt(self):
        return DEV_SYSTEM_PROMPT

    @property
    def tools(self):
        return [
            # Dev-specific interactive tools
            TOOL_ASK_USER,
            TOOL_NOTIFY_USER,
            TOOL_PROJECT_SCAN,
            TOOL_MULTI_EDIT,
            TOOL_DIFF_PREVIEW,
            TOOL_TEST_LOOP,
            TOOL_FIND_REFERENCES,
            TOOL_ROLLBACK,
            # Standard coding tools
            TOOL_RUN_COMMAND,
            TOOL_READ_FILE,
            TOOL_WRITE_FILE,
            TOOL_EDIT_FILE,
            TOOL_LIST_DIR,
            TOOL_SEARCH_FILES,
            TOOL_GIT,
            TOOL_INSTALL_PACKAGE,
            TOOL_RUN_TESTS,
            # Terminal
            TOOL_DONE,
            TOOL_STUCK,
        ]

    # ═══════════════════════════════════════════════════════
    #  Tool Dispatch
    # ═══════════════════════════════════════════════════════

    def _dispatch(self, name, inp):
        """Route dev tool calls to handlers."""
        try:
            # ── Dev-specific tools ──
            if name == "ask_user":
                return self._ask_user(inp["message"], inp.get("timeout", 300))

            elif name == "notify_user":
                return self._notify_user(inp["message"])

            elif name == "project_scan":
                return self._project_scan(inp["path"], inp.get("depth", 4))

            elif name == "multi_edit":
                return self._multi_edit(inp["edits"])

            elif name == "diff_preview":
                return self._diff_preview(
                    inp["path"], inp["old_string"], inp["new_string"]
                )

            elif name == "test_loop":
                return self._test_loop(
                    inp["test_command"],
                    inp.get("max_attempts", 5),
                    inp.get("project_path"),
                )

            elif name == "find_references":
                return self._find_references(
                    inp["symbol"],
                    inp["directory"],
                    inp.get("file_types", "py,js,ts,jsx,tsx"),
                )

            elif name == "rollback":
                return self._rollback(inp["action"], inp.get("file_path"))

            # ── Standard coding tools (same as coder agent) ──
            elif name == "run_command":
                result = run_terminal(inp["command"], timeout=inp.get("timeout", 60))
                return result.get("content", str(result))

            elif name == "read_file":
                result = read_file(inp["path"])
                return result.get("content", str(result))

            elif name == "write_file":
                result = write_file(inp["path"], inp["content"])
                self._changes_made.append(f"Created: {inp['path']}")
                return result.get("content", str(result))

            elif name == "edit_file":
                result = self._edit_file(inp["path"], inp["old_string"], inp["new_string"])
                if "✅" in result:
                    self._changes_made.append(f"Edited: {inp['path']}")
                return result

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
                result = run_terminal(f"git {inp['command']}", timeout=30)
                content = result.get("content", str(result))
                cmd = inp["command"].strip()
                if cmd.startswith("commit"):
                    self._changes_made.append(f"Committed: {cmd}")
                elif cmd.startswith("push"):
                    self._changes_made.append(f"Pushed: {cmd}")
                return content

            elif name == "install_package":
                mgr = inp.get("manager", "pip")
                pkg = inp["package"]
                cmd_map = {
                    "pip": f"pip install {pkg}",
                    "pip3": f"pip3 install {pkg}",
                    "npm": f"npm install {pkg}",
                    "brew": f"brew install {pkg}",
                }
                cmd = cmd_map.get(mgr, f"pip install {pkg}")
                result = run_terminal(cmd, timeout=120)
                return result.get("content", str(result))

            elif name == "run_tests":
                result = run_terminal(inp["command"], timeout=inp.get("timeout", 120))
                return result.get("content", str(result))

            return f"Unknown dev tool: {name}"
        except Exception as e:
            return f"ERROR: {e}"

    # ═══════════════════════════════════════════════════════
    #  Interactive iMessage Tools
    # ═══════════════════════════════════════════════════════

    def _ask_user(self, message, timeout=300):
        """Send a question via iMessage and wait for the user's reply."""
        if not self._imessage_sender or not self._imessage_reader:
            return "ERROR: iMessage not configured for dev agent. Cannot ask user."

        # Prefix so user knows it's the dev agent
        tagged = f"🛠️ Dev Agent:\n{message}"

        try:
            self._imessage_sender.send(tagged)
        except Exception as e:
            return f"ERROR sending iMessage: {e}"

        print(f"    📱 [Dev Agent] Asked user: {message[:100]}...")
        print(f"    ⏳ Waiting for reply ({timeout}s timeout)...")

        try:
            reply = self._imessage_reader.wait_for_reply(timeout=timeout)
            if reply.get("success"):
                user_reply = reply["content"]
                print(f"    📱 [Dev Agent] User replied: {user_reply[:100]}...")
                return f"User replied: {user_reply}"
            else:
                print(f"    ⏰ [Dev Agent] No reply within {timeout}s")
                return f"No reply received within {timeout}s. Continue with your best judgment or try asking again."
        except Exception as e:
            return f"ERROR waiting for reply: {e}"

    def _notify_user(self, message):
        """Send a one-way status update via iMessage (no wait)."""
        if not self._imessage_sender:
            return "ERROR: iMessage not configured for dev agent."

        tagged = f"🛠️ Dev Agent:\n{message}"

        try:
            self._imessage_sender.send(tagged)
            print(f"    📱 [Dev Agent] Notified: {message[:100]}...")
            return "✅ Notification sent."
        except Exception as e:
            return f"ERROR sending notification: {e}"

    # ═══════════════════════════════════════════════════════
    #  Project Intelligence
    # ═══════════════════════════════════════════════════════

    def _project_scan(self, path, depth=4):
        """Deep scan a project to understand its structure, stack, and conventions."""
        path = os.path.expanduser(path)
        if not os.path.isdir(path):
            return f"ERROR: Not a directory: {path}"

        # Check cache
        if path in self._project_cache:
            return f"(Cached) {self._project_cache[path]}"

        sections = []
        sections.append(f"## Project Scan: {path}\n")

        # 1. Directory tree
        try:
            result = run_terminal(
                f"find '{path}' -maxdepth {depth} "
                f"-not -path '*/node_modules/*' "
                f"-not -path '*/.git/*' "
                f"-not -path '*/venv/*' "
                f"-not -path '*/__pycache__/*' "
                f"-not -path '*/.next/*' "
                f"-not -path '*/dist/*' "
                f"-not -path '*/build/*' "
                f"| head -200",
                timeout=10,
            )
            tree = result.get("content", "")
            sections.append(f"### Directory Structure\n```\n{tree}\n```\n")
        except Exception:
            sections.append("### Directory Structure\n(scan failed)\n")

        # 2. Tech stack detection
        stack = []
        key_files = {
            "package.json": "Node.js/JavaScript",
            "tsconfig.json": "TypeScript",
            "requirements.txt": "Python (pip)",
            "setup.py": "Python (setuptools)",
            "pyproject.toml": "Python (modern)",
            "Cargo.toml": "Rust",
            "go.mod": "Go",
            "Gemfile": "Ruby",
            "pom.xml": "Java (Maven)",
            "build.gradle": "Java/Kotlin (Gradle)",
            "Makefile": "Make",
            "Dockerfile": "Docker",
            "docker-compose.yml": "Docker Compose",
            "docker-compose.yaml": "Docker Compose",
            ".env": "Environment Variables",
            "next.config.js": "Next.js",
            "next.config.mjs": "Next.js",
            "next.config.ts": "Next.js",
            "vite.config.ts": "Vite",
            "vite.config.js": "Vite",
            "tailwind.config.js": "Tailwind CSS",
            "tailwind.config.ts": "Tailwind CSS",
            ".eslintrc.js": "ESLint",
            ".eslintrc.json": "ESLint",
            "jest.config.js": "Jest",
            "jest.config.ts": "Jest",
            "pytest.ini": "Pytest",
            "setup.cfg": "Python config",
            "tox.ini": "Tox (Python testing)",
            ".flake8": "Flake8 (Python linting)",
            "webpack.config.js": "Webpack",
        }

        for filename, tech in key_files.items():
            if os.path.exists(os.path.join(path, filename)):
                stack.append(tech)

        if stack:
            sections.append(f"### Tech Stack\n{', '.join(stack)}\n")

        # 3. Read key config files
        configs_to_read = [
            "package.json", "requirements.txt", "pyproject.toml",
            "tsconfig.json", "Cargo.toml", "go.mod",
        ]
        for cfg_name in configs_to_read:
            cfg_path = os.path.join(path, cfg_name)
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Truncate large configs
                    if len(content) > 3000:
                        content = content[:3000] + "\n... (truncated)"
                    sections.append(f"### {cfg_name}\n```\n{content}\n```\n")
                except Exception:
                    pass

        # 4. README
        for readme_name in ["README.md", "README.txt", "README", "readme.md"]:
            readme_path = os.path.join(path, readme_name)
            if os.path.exists(readme_path):
                try:
                    with open(readme_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if len(content) > 2000:
                        content = content[:2000] + "\n... (truncated)"
                    sections.append(f"### README\n{content}\n")
                except Exception:
                    pass
                break

        # 5. Git status
        try:
            result = run_terminal(f"cd '{path}' && git status --short 2>/dev/null | head -30", timeout=5)
            git_status = result.get("content", "").strip()
            if git_status:
                sections.append(f"### Git Status\n```\n{git_status}\n```\n")

            result = run_terminal(f"cd '{path}' && git log --oneline -10 2>/dev/null", timeout=5)
            git_log = result.get("content", "").strip()
            if git_log:
                sections.append(f"### Recent Commits\n```\n{git_log}\n```\n")

            result = run_terminal(f"cd '{path}' && git branch -a 2>/dev/null | head -20", timeout=5)
            branches = result.get("content", "").strip()
            if branches:
                sections.append(f"### Branches\n```\n{branches}\n```\n")
        except Exception:
            pass

        # 6. Entry points and test files
        try:
            result = run_terminal(
                f"find '{path}' -maxdepth 3 "
                f"\\( -name 'main.py' -o -name 'app.py' -o -name 'index.ts' "
                f"-o -name 'index.js' -o -name 'server.py' -o -name 'server.ts' "
                f"-o -name 'main.ts' -o -name 'main.go' -o -name 'main.rs' "
                f"-o -name 'App.tsx' -o -name 'App.jsx' \\) "
                f"-not -path '*/node_modules/*' -not -path '*/.git/*' "
                f"2>/dev/null",
                timeout=5,
            )
            entry_points = result.get("content", "").strip()
            if entry_points:
                sections.append(f"### Entry Points\n```\n{entry_points}\n```\n")
        except Exception:
            pass

        try:
            result = run_terminal(
                f"find '{path}' -maxdepth 4 "
                f"\\( -name 'test_*.py' -o -name '*_test.py' -o -name '*.test.ts' "
                f"-o -name '*.test.js' -o -name '*.spec.ts' -o -name '*.spec.js' "
                f"-o -name '*_test.go' \\) "
                f"-not -path '*/node_modules/*' -not -path '*/.git/*' "
                f"2>/dev/null | head -20",
                timeout=5,
            )
            test_files = result.get("content", "").strip()
            if test_files:
                sections.append(f"### Test Files\n```\n{test_files}\n```\n")
        except Exception:
            pass

        # 7. File stats
        try:
            result = run_terminal(
                f"find '{path}' -type f "
                f"-not -path '*/node_modules/*' -not -path '*/.git/*' "
                f"-not -path '*/venv/*' -not -path '*/__pycache__/*' "
                f"2>/dev/null | wc -l",
                timeout=5,
            )
            file_count = result.get("content", "").strip()

            result = run_terminal(
                f"find '{path}' -type f -name '*.py' -o -name '*.js' -o -name '*.ts' "
                f"-o -name '*.tsx' -o -name '*.jsx' -o -name '*.go' -o -name '*.rs' "
                f"2>/dev/null | "
                f"grep -v node_modules | grep -v .git | grep -v venv | "
                f"xargs wc -l 2>/dev/null | tail -1",
                timeout=10,
            )
            loc = result.get("content", "").strip()
            sections.append(f"### Stats\n- Files: {file_count}\n- Lines of code: {loc}\n")
        except Exception:
            pass

        scan_result = "\n".join(sections)
        self._project_cache[path] = scan_result
        return scan_result

    # ═══════════════════════════════════════════════════════
    #  Advanced Editing
    # ═══════════════════════════════════════════════════════

    def _multi_edit(self, edits):
        """Apply multiple edits atomically — validate all before applying any."""
        if not edits:
            return "ERROR: No edits provided."

        # Phase 1: Validate all edits
        file_contents = {}
        for i, edit in enumerate(edits):
            path = os.path.expanduser(edit["path"])
            old_str = edit["old_string"]

            if path not in file_contents:
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        file_contents[path] = f.read()
                except FileNotFoundError:
                    return f"ERROR: File not found: {path} (edit #{i + 1}). No edits applied."
                except Exception as e:
                    return f"ERROR: Cannot read {path}: {e}. No edits applied."

            if old_str not in file_contents[path]:
                return (
                    f"ERROR: old_string not found in {path} (edit #{i + 1}). "
                    f"No edits applied. Use read_file to check current contents.\n"
                    f"Looking for: {old_str[:200]}"
                )

            count = file_contents[path].count(old_str)
            if count > 1:
                return (
                    f"ERROR: old_string found {count} times in {path} (edit #{i + 1}). "
                    f"Make it more specific. No edits applied."
                )

        # Phase 2: Apply all edits
        applied = []
        for edit in edits:
            path = os.path.expanduser(edit["path"])
            old_str = edit["old_string"]
            new_str = edit["new_string"]

            content = file_contents[path]
            file_contents[path] = content.replace(old_str, new_str, 1)

        # Phase 3: Write all files
        for path, content in file_contents.items():
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                applied.append(path)
            except Exception as e:
                return f"ERROR: Failed writing {path}: {e}. Some edits may have been partially applied!"

        self._changes_made.extend([f"Multi-edited: {p}" for p in applied])

        unique_files = list(set(os.path.basename(p) for p in applied))
        return (
            f"✅ Applied {len(edits)} edit(s) across {len(applied)} file(s): "
            f"{', '.join(unique_files)}"
        )

    def _diff_preview(self, path, old_string, new_string):
        """Generate a unified diff preview without applying changes."""
        path = os.path.expanduser(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                original = f.read()
        except FileNotFoundError:
            return f"ERROR: File not found: {path}"

        if old_string not in original:
            return f"ERROR: old_string not found in {path}. Use read_file to check."

        modified = original.replace(old_string, new_string, 1)

        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=f"a/{os.path.basename(path)}",
            tofile=f"b/{os.path.basename(path)}",
            n=3,
        )
        diff_text = "".join(diff)

        if not diff_text:
            return "No changes detected (old_string and new_string are identical)."

        # Count changes
        added = sum(1 for line in diff_text.splitlines() if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff_text.splitlines() if line.startswith("-") and not line.startswith("---"))

        return (
            f"## Diff Preview: {os.path.basename(path)}\n"
            f"+{added} lines / -{removed} lines\n\n"
            f"```diff\n{diff_text}\n```\n\n"
            f"(This is a PREVIEW — changes have NOT been applied)"
        )

    # ═══════════════════════════════════════════════════════
    #  Test-Driven Development Loop
    # ═══════════════════════════════════════════════════════

    def _test_loop(self, test_command, max_attempts=5, project_path=None):
        """Run tests, diagnose failures, fix, and re-test automatically."""
        results_log = []
        fixes_applied = []

        for attempt in range(1, max_attempts + 1):
            print(f"    🧪 [Dev Agent] Test attempt {attempt}/{max_attempts}")

            # Run the tests
            result = run_terminal(test_command, timeout=120)
            output = result.get("content", str(result))
            exit_code = result.get("exit_code", -1)

            results_log.append(f"Attempt {attempt}: exit_code={exit_code}")

            # Check if tests passed
            if exit_code == 0:
                summary = (
                    f"✅ All tests passed on attempt {attempt}/{max_attempts}.\n"
                    f"Command: {test_command}\n"
                )
                if fixes_applied:
                    summary += f"\nFixes applied ({len(fixes_applied)}):\n"
                    for fix in fixes_applied:
                        summary += f"  - {fix}\n"
                summary += f"\nFinal output:\n{output[-2000:]}"
                return summary

            # Tests failed — return the failure info for the LLM to diagnose
            if attempt < max_attempts:
                # Return info so the LLM can fix it in the next step
                return (
                    f"❌ Tests FAILED (attempt {attempt}/{max_attempts}).\n"
                    f"Command: {test_command}\n"
                    f"Exit code: {exit_code}\n\n"
                    f"Error output:\n{output[-4000:]}\n\n"
                    f"Analyze the error, fix the code, then call test_loop again "
                    f"(remaining attempts: {max_attempts - attempt})."
                )

        # All attempts exhausted
        return (
            f"❌ Tests still failing after {max_attempts} attempts.\n"
            f"Command: {test_command}\n\n"
            f"Last output:\n{output[-4000:]}\n\n"  # noqa: F821
            f"Fixes attempted:\n" + "\n".join(f"  - {f}" for f in fixes_applied)
        )

    # ═══════════════════════════════════════════════════════
    #  Code Intelligence
    # ═══════════════════════════════════════════════════════

    def _find_references(self, symbol, directory, file_types="py,js,ts,jsx,tsx"):
        """Find all references to a symbol across the project."""
        directory = os.path.expanduser(directory)

        # Build grep include flags
        extensions = [ext.strip() for ext in file_types.split(",")]
        include_flags = " ".join(f"--include='*.{ext}'" for ext in extensions)

        result = run_terminal(
            f"grep -rn {include_flags} "
            f"--exclude-dir=node_modules --exclude-dir=.git "
            f"--exclude-dir=venv --exclude-dir=__pycache__ "
            f"--exclude-dir=dist --exclude-dir=build "
            f"'\\b{symbol}\\b' '{directory}' 2>/dev/null | head -60",
            timeout=15,
        )
        output = result.get("content", "").strip()

        if not output:
            return f"No references to '{symbol}' found in {directory}"

        lines = output.strip().splitlines()
        return (
            f"## References to '{symbol}' ({len(lines)} found)\n\n"
            f"```\n{output}\n```\n\n"
            f"{'⚠️ Results truncated to 60 matches.' if len(lines) >= 60 else ''}"
        )

    def _rollback(self, action, file_path=None):
        """Undo changes using git."""
        if action == "last_commit":
            result = run_terminal("git reset --soft HEAD~1", timeout=10)
            content = result.get("content", str(result))
            self._changes_made.append("Rolled back last commit")
            return f"✅ Last commit undone (changes kept staged).\n{content}"

        elif action == "file":
            if not file_path:
                return "ERROR: file_path required for action='file'"
            result = run_terminal(f"git checkout -- '{file_path}'", timeout=10)
            content = result.get("content", str(result))
            self._changes_made.append(f"Rolled back: {file_path}")
            return f"✅ Restored {file_path} to last committed state.\n{content}"

        elif action == "all":
            result = run_terminal("git checkout -- . && git clean -fd", timeout=10)
            content = result.get("content", str(result))
            self._changes_made.append("Rolled back ALL changes")
            return f"⚠️ ALL uncommitted changes discarded.\n{content}"

        return f"ERROR: Unknown rollback action: {action}"

    # ═══════════════════════════════════════════════════════
    #  Standard File Tools (shared with coder agent)
    # ═══════════════════════════════════════════════════════

    def _edit_file(self, path, old_string, new_string):
        """Surgical string replacement in a file."""
        try:
            path = os.path.expanduser(path)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            if old_string not in content:
                return f"ERROR: old_string not found in {path}. Use read_file to see current contents."

            count = content.count(old_string)
            if count > 1:
                return (
                    f"ERROR: old_string found {count} times in {path}. "
                    f"Make it more specific (include surrounding lines)."
                )

            new_content = content.replace(old_string, new_string, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"✅ Edited {path} — replaced {len(old_string)} chars with {len(new_string)} chars"
        except FileNotFoundError:
            return f"ERROR: File not found: {path}"
        except Exception as e:
            return f"ERROR editing file: {e}"

    def _search_files(self, pattern, directory, content_search):
        """Search files by name or content."""
        try:
            directory = os.path.expanduser(directory)
            if content_search:
                result = run_terminal(
                    f"grep -rn --include='*.py' --include='*.js' --include='*.ts' "
                    f"--include='*.tsx' --include='*.jsx' --include='*.html' "
                    f"--include='*.css' --include='*.json' --include='*.yaml' "
                    f"--include='*.yml' --include='*.md' --include='*.txt' "
                    f"'{pattern}' '{directory}' 2>/dev/null | head -50",
                    timeout=15,
                )
                return result.get("content", "(no results)")
            else:
                result = run_terminal(
                    f"find '{directory}' -name '{pattern}' "
                    f"-not -path '*/node_modules/*' -not -path '*/.git/*' "
                    f"-not -path '*/venv/*' 2>/dev/null | head -50",
                    timeout=15,
                )
                return result.get("content", "(no results)")
        except Exception as e:
            return f"ERROR searching: {e}"
