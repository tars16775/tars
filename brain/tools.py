"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Brain: Orchestrator Tool Definitions             ║
╠══════════════════════════════════════════════════════════════╣
║  The brain doesn't do tasks itself — it DEPLOYS AGENTS.      ║
║  These tools let the brain deploy agents, communicate with   ║
║  the user, manage memory, and do quick checks.               ║
╚══════════════════════════════════════════════════════════════╝
"""

TARS_TOOLS = [
    # ═══════════════════════════════════════
    #  Agent Deployment
    # ═══════════════════════════════════════
    {
        "name": "deploy_browser_agent",
        "description": "Deploy the Browser Agent for web tasks. It controls Chrome physically (mouse + keyboard) and can: navigate URLs, fill forms, click buttons, sign up for accounts, interact with any website, read page content. Give it a DETAILED task description with all needed info (URLs, form values, credentials, etc).",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Detailed browser task. Include: URLs, form values, credentials, what to click, what 'done' looks like."
                }
            },
            "required": ["task"]
        }
    },
    {
        "name": "deploy_coder_agent",
        "description": "Deploy the Coder Agent for software development tasks. It can: write code in any language, build projects, debug, run tests, git operations, install packages, deploy. Give it a DETAILED task with requirements, tech stack, file paths, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Detailed coding task. Include: requirements, tech stack, file paths, expected behavior, what 'done' looks like."
                }
            },
            "required": ["task"]
        }
    },
    {
        "name": "deploy_system_agent",
        "description": "Deploy the System Agent for macOS automation. It can: open apps, type text, press keyboard shortcuts, click at coordinates, take screenshots, run AppleScript, manage system settings. Give it a specific task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Detailed system task. Include: app names, what to do in each app, expected result."
                }
            },
            "required": ["task"]
        }
    },
    {
        "name": "deploy_research_agent",
        "description": "Deploy the Research Agent for information gathering. It can: search Google, read web pages, extract specific info, cross-reference sources, compile findings. Give it a clear research question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Research question or information to find. Be specific about what details you need."
                }
            },
            "required": ["task"]
        }
    },
    {
        "name": "deploy_file_agent",
        "description": "Deploy the File Agent for file management. It can: find files, organize directories, compress/extract archives, clean up, check disk usage, move/copy/delete files. Give it a specific file operation task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "File management task. Include: paths, patterns to match, where to move things, etc."
                }
            },
            "required": ["task"]
        }
    },

    # ═══════════════════════════════════════
    #  Direct Tools (no agent needed)
    # ═══════════════════════════════════════
    {
        "name": "send_imessage",
        "description": "Send an iMessage to Abdullah. Use to report progress, results, ask questions. Keep messages concise and use emojis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The message to send"}
            },
            "required": ["message"]
        }
    },
    {
        "name": "wait_for_reply",
        "description": "Wait for Abdullah to reply via iMessage. Use after asking a question. Blocks until reply received.",
        "input_schema": {
            "type": "object",
            "properties": {
                "timeout": {"type": "integer", "description": "Max seconds to wait (default 300)", "default": 300}
            },
            "required": []
        }
    },
    {
        "name": "save_memory",
        "description": "Save information to memory for later recall. Categories: preference, project, context, note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["preference", "project", "context", "note"]},
                "key": {"type": "string", "description": "Short label"},
                "value": {"type": "string", "description": "Information to remember"}
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "recall_memory",
        "description": "Search memory for relevant information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "run_quick_command",
        "description": "Run a simple, quick shell command for fast checks. NOT for complex tasks — use deploy_coder_agent or deploy_system_agent for those. Good for: 'ls', 'pwd', 'date', 'cat file.txt', etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Simple shell command"},
                "timeout": {"type": "integer", "description": "Timeout seconds (default 30)", "default": 30}
            },
            "required": ["command"]
        }
    },
    {
        "name": "quick_read_file",
        "description": "Quickly read a file. For simple checks, not bulk operations. Use deploy_file_agent for complex file tasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "think",
        "description": "Think through a complex problem step by step before acting. Use this to plan multi-agent workflows, analyze agent failures, or reason about the best approach. Your thinking will be logged but not sent to the user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thought": {"type": "string", "description": "Your reasoning and analysis"}
            },
            "required": ["thought"]
        }
    },
]
