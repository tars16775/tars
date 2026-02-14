"""
╔══════════════════════════════════════════════════════════════╗
║     TARS — Shared Agent Tool Definitions                     ║
╠══════════════════════════════════════════════════════════════╣
║  Common tool schemas reused across multiple agents.          ║
║  Single source of truth — no duplication.                    ║
╚══════════════════════════════════════════════════════════════╝
"""


# ─────────────────────────────────────────────
#  Terminal Tools (done + stuck are auto-added by BaseAgent)
# ─────────────────────────────────────────────

TOOL_DONE = {
    "name": "done",
    "description": "Task is complete. Provide a detailed summary of what was accomplished, including specifics (files created, commands run, results found, etc).",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Detailed summary of accomplishments"
            }
        },
        "required": ["summary"]
    }
}

TOOL_STUCK = {
    "name": "stuck",
    "description": "Cannot complete the task after trying multiple approaches. Explain exactly what you tried and why each approach failed. The orchestrator brain will analyze this and either retry with guidance, reroute to a different agent, or ask the user.",
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Detailed explanation: what you tried, why each approach failed, what info is missing"
            }
        },
        "required": ["reason"]
    }
}


# ─────────────────────────────────────────────
#  File Tools (shared by Coder, System, File agents)
# ─────────────────────────────────────────────

TOOL_READ_FILE = {
    "name": "read_file",
    "description": "Read the full contents of a file. Use absolute paths.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"}
        },
        "required": ["path"]
    }
}

TOOL_WRITE_FILE = {
    "name": "write_file",
    "description": "Write content to a file. Creates parent directories automatically. Overwrites if file exists.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"},
            "content": {"type": "string", "description": "Full file content to write"}
        },
        "required": ["path", "content"]
    }
}

TOOL_EDIT_FILE = {
    "name": "edit_file",
    "description": "Surgically edit a file by replacing an exact string with new content. Use read_file first to see the current content. The old_string must match EXACTLY (whitespace, indentation, everything).",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"},
            "old_string": {"type": "string", "description": "Exact text to find and replace (must be unique in file)"},
            "new_string": {"type": "string", "description": "Replacement text"}
        },
        "required": ["path", "old_string", "new_string"]
    }
}

TOOL_LIST_DIR = {
    "name": "list_dir",
    "description": "List contents of a directory with file sizes.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to directory"}
        },
        "required": ["path"]
    }
}


# ─────────────────────────────────────────────
#  Terminal / Shell Tools
# ─────────────────────────────────────────────

TOOL_RUN_COMMAND = {
    "name": "run_command",
    "description": "Run a shell command (bash/zsh) and get the output. Use for: installing packages, running scripts, git, building, any CLI task. For long commands, set a higher timeout.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)", "default": 60}
        },
        "required": ["command"]
    }
}

TOOL_SEARCH_FILES = {
    "name": "search_files",
    "description": "Search for files by name pattern (glob) or search file contents (grep). Returns matching file paths and, for content searches, the matching lines.",
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Search pattern — filename glob (e.g. '*.py', '*.ts') or text to grep for"},
            "directory": {"type": "string", "description": "Directory to search in (default: current dir)"},
            "content_search": {"type": "boolean", "description": "If true, search inside file contents (grep). If false, search filenames.", "default": False}
        },
        "required": ["pattern"]
    }
}


# ─────────────────────────────────────────────
#  Git Tools
# ─────────────────────────────────────────────

TOOL_GIT = {
    "name": "git",
    "description": "Run a git command. Examples: 'status', 'add .', 'commit -m \"msg\"', 'push', 'pull', 'log --oneline -10', 'diff', 'branch', 'checkout -b feature'. Do NOT include 'git' prefix — just the subcommand.",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Git subcommand (without 'git' prefix)"}
        },
        "required": ["command"]
    }
}


# ─────────────────────────────────────────────
#  Package Management
# ─────────────────────────────────────────────

TOOL_INSTALL_PACKAGE = {
    "name": "install_package",
    "description": "Install a package using the appropriate package manager.",
    "input_schema": {
        "type": "object",
        "properties": {
            "package": {"type": "string", "description": "Package name to install"},
            "manager": {"type": "string", "enum": ["pip", "npm", "brew", "pip3"], "description": "Package manager", "default": "pip"}
        },
        "required": ["package"]
    }
}


# ─────────────────────────────────────────────
#  Test Runner
# ─────────────────────────────────────────────

TOOL_RUN_TESTS = {
    "name": "run_tests",
    "description": "Run tests for the project. Provide the test command (e.g., 'pytest', 'npm test', 'python -m unittest').",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Test command to run"},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default 120)", "default": 120}
        },
        "required": ["command"]
    }
}


# ─────────────────────────────────────────────
#  Mac Control Tools
# ─────────────────────────────────────────────

TOOL_OPEN_APP = {
    "name": "open_app",
    "description": "Open a macOS application by name. Examples: 'Safari', 'Terminal', 'Visual Studio Code', 'Finder', 'Spotify'",
    "input_schema": {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "Application name"}
        },
        "required": ["app_name"]
    }
}

TOOL_TYPE_TEXT = {
    "name": "type_text",
    "description": "Type text into the currently active/frontmost application window using physical keyboard.",
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to type"}
        },
        "required": ["text"]
    }
}

TOOL_KEY_PRESS = {
    "name": "key_press",
    "description": "Press a keyboard shortcut. Format: 'command+s', 'command+shift+p', 'return', 'tab', 'escape'. Use modifier names: command/cmd, control/ctrl, option/alt, shift.",
    "input_schema": {
        "type": "object",
        "properties": {
            "keys": {"type": "string", "description": "Key combination (e.g., 'command+s', 'return')"}
        },
        "required": ["keys"]
    }
}

TOOL_CLICK = {
    "name": "click",
    "description": "Click at a specific screen coordinate using physical mouse.",
    "input_schema": {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "X screen coordinate"},
            "y": {"type": "integer", "description": "Y screen coordinate"},
            "double_click": {"type": "boolean", "description": "Double-click", "default": False}
        },
        "required": ["x", "y"]
    }
}

TOOL_SCREENSHOT = {
    "name": "screenshot",
    "description": "Take a screenshot of the entire screen. Returns the saved file path.",
    "input_schema": {"type": "object", "properties": {}}
}

TOOL_FRONTMOST_APP = {
    "name": "frontmost_app",
    "description": "Get the name of the currently active/frontmost application.",
    "input_schema": {"type": "object", "properties": {}}
}

TOOL_APPLESCRIPT = {
    "name": "applescript",
    "description": "Run raw AppleScript code for advanced macOS automation. Use for things like: controlling System Preferences, managing windows, interacting with apps that have AppleScript dictionaries.",
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "AppleScript code to execute"}
        },
        "required": ["code"]
    }
}


# ─────────────────────────────────────────────
#  Research / Web Tools
# ─────────────────────────────────────────────

TOOL_WEB_SEARCH = {
    "name": "web_search",
    "description": "Quick Google search. Returns search result snippets. For simple fact lookups.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"}
        },
        "required": ["query"]
    }
}

TOOL_BROWSE = {
    "name": "browse",
    "description": "Open a URL in the browser and read the full page text. For reading articles, documentation, product pages.",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to visit and read"}
        },
        "required": ["url"]
    }
}

TOOL_EXTRACT = {
    "name": "extract",
    "description": "Open a URL and extract specific information by answering a question about the page content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to visit"},
            "question": {"type": "string", "description": "What specific info to extract from the page"}
        },
        "required": ["url", "question"]
    }
}


# ─────────────────────────────────────────────
#  Research Note Tools
# ─────────────────────────────────────────────

TOOL_NOTE = {
    "name": "note",
    "description": "Save a research finding to your working notes. Use to collect facts as you research.",
    "input_schema": {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Short label for this finding"},
            "value": {"type": "string", "description": "The finding/fact to save"}
        },
        "required": ["key", "value"]
    }
}

TOOL_NOTES = {
    "name": "notes",
    "description": "Review all your collected research notes so far.",
    "input_schema": {"type": "object", "properties": {}}
}


# ─────────────────────────────────────────────
#  File Management Tools
# ─────────────────────────────────────────────

TOOL_MOVE = {
    "name": "move",
    "description": "Move or rename a file or directory.",
    "input_schema": {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Source path"},
            "destination": {"type": "string", "description": "Destination path"}
        },
        "required": ["source", "destination"]
    }
}

TOOL_COPY = {
    "name": "copy",
    "description": "Copy a file or directory.",
    "input_schema": {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Source path"},
            "destination": {"type": "string", "description": "Destination path"}
        },
        "required": ["source", "destination"]
    }
}

TOOL_DELETE = {
    "name": "delete",
    "description": "Delete a file or directory. Use carefully.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to delete"},
            "recursive": {"type": "boolean", "description": "Delete directory recursively", "default": False}
        },
        "required": ["path"]
    }
}

TOOL_TREE = {
    "name": "tree",
    "description": "Show directory tree structure with depth limit.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Directory path"},
            "depth": {"type": "integer", "description": "Max depth (default 3)", "default": 3}
        },
        "required": ["path"]
    }
}

TOOL_DISK_USAGE = {
    "name": "disk_usage",
    "description": "Get disk usage / size of a file or directory.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to check"}
        },
        "required": ["path"]
    }
}

TOOL_COMPRESS = {
    "name": "compress",
    "description": "Compress files/directories into a zip or tar.gz archive.",
    "input_schema": {
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file/directory paths to compress"
            },
            "output": {"type": "string", "description": "Output archive path (e.g., 'backup.zip', 'project.tar.gz')"}
        },
        "required": ["paths", "output"]
    }
}

TOOL_EXTRACT_ARCHIVE = {
    "name": "extract_archive",
    "description": "Extract a zip, tar, or tar.gz archive.",
    "input_schema": {
        "type": "object",
        "properties": {
            "archive": {"type": "string", "description": "Path to archive file"},
            "destination": {"type": "string", "description": "Directory to extract into"}
        },
        "required": ["archive", "destination"]
    }
}
