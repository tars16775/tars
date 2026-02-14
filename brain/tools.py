"""
╔══════════════════════════════════════════╗
║       TARS — Brain: Tool Definitions     ║
╚══════════════════════════════════════════╝

Tool schemas for Claude's tool_use API.
These define what actions TARS can take.
"""

TARS_TOOLS = [
    {
        "name": "run_terminal",
        "description": "Run a shell command in the terminal and return the output. Use for: installing packages, running scripts, git commands, building projects, any CLI task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute (bash/zsh)"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 60)",
                    "default": 60
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "open_app",
        "description": "Open a macOS application by name. Examples: 'Safari', 'Terminal', 'Visual Studio Code', 'Finder'",
        "input_schema": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "The name of the application to open"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "type_text",
        "description": "Type text into the currently active/frontmost window. Use for entering text in any application.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to type"
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "key_press",
        "description": "Press a keyboard shortcut. Use modifier names: command, control, option, shift. Examples: 'command+s', 'command+shift+p', 'return', 'tab'",
        "input_schema": {
            "type": "object",
            "properties": {
                "keys": {
                    "type": "string",
                    "description": "The key combination (e.g., 'command+s', 'return', 'command+shift+p')"
                }
            },
            "required": ["keys"]
        }
    },
    {
        "name": "click",
        "description": "Click at a specific screen coordinate.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate"},
                "y": {"type": "integer", "description": "Y coordinate"},
                "double_click": {
                    "type": "boolean",
                    "description": "Whether to double-click",
                    "default": False
                }
            },
            "required": ["x", "y"]
        }
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file at the given path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to read"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. Creates parent directories automatically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file"
                }
            },
            "required": ["file_path", "content"]
        }
    },
    {
        "name": "move_file",
        "description": "Move or rename a file or directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source path"},
                "destination": {"type": "string", "description": "Destination path"}
            },
            "required": ["source", "destination"]
        }
    },
    {
        "name": "delete_file",
        "description": "Delete a file or directory. DESTRUCTIVE — will ask for confirmation if safety is enabled.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file or directory to delete"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to delete directories recursively",
                    "default": False
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "list_directory",
        "description": "List contents of a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dir_path": {
                    "type": "string",
                    "description": "Absolute path to the directory"
                }
            },
            "required": ["dir_path"]
        }
    },
    # ═══════════════════════════════════════
    #  BROWSER — Agentic (sub-brain)
    # ═══════════════════════════════════════
    {
        "name": "web_task",
        "description": "Give a browser task to the autonomous Browser Agent. The agent has its own AI brain and will figure out all the clicking, typing, form-filling, and navigation on its own. Give it a detailed, specific goal. Examples: 'Go to gmail.com and create a new account with first name TARS, last name Bot, birthday June 15 1990, gender Male, desired email tarsbot123', 'Go to amazon.com and search for wireless headphones, find the best rated one under $50, and tell me the name and price', 'Log into twitter.com with username X and password Y and post a tweet saying Hello World'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Detailed browser task description. Be specific: include URLs, form values, account details, search terms, etc. The browser agent will handle all the steps autonomously."
                }
            },
            "required": ["task"]
        }
    },
    {
        "name": "web_search",
        "description": "Quick Google search. Returns the search results text directly. For simple lookups where you don't need to click into results. For anything more complex (clicking results, filling forms, multi-step), use web_task instead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "take_screenshot",
        "description": "Take a screenshot of the current screen (entire Mac display). Returns the file path of the saved screenshot.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "send_imessage",
        "description": "Send an iMessage to Abdullah. Use to report progress, ask questions, or share results. Keep messages concise.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to send via iMessage"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "wait_for_reply",
        "description": "Wait for Abdullah to reply via iMessage. Blocks until a new message is received. Use after sending a question via iMessage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "timeout": {
                    "type": "integer",
                    "description": "Max seconds to wait (default 300 = 5 min)",
                    "default": 300
                }
            },
            "required": []
        }
    },
    {
        "name": "save_memory",
        "description": "Save information to TARS's memory for later recall. Use for preferences, project notes, learned patterns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["preference", "project", "context", "note"],
                    "description": "Category of memory"
                },
                "key": {
                    "type": "string",
                    "description": "A short label for this memory"
                },
                "value": {
                    "type": "string",
                    "description": "The information to remember"
                }
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "recall_memory",
        "description": "Search TARS's memory for relevant information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for in memory"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_frontmost_app",
        "description": "Get the name of the currently active/frontmost application.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
]
