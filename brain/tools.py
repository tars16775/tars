"""
╔══════════════════════════════════════════════════════════════╗
║      TARS — Brain: Orchestrator Tool Definitions             ║
╠══════════════════════════════════════════════════════════════╣
║  The brain doesn't do tasks itself — it DEPLOYS AGENTS.      ║
║  These tools let the brain deploy agents, communicate with   ║
║  the user, manage memory, scan the environment, verify       ║
║  results, and checkpoint progress.                           ║
║                                                              ║
║  Phase 1-5 tools for full autonomy.                          ║
╚══════════════════════════════════════════════════════════════╝
"""

TARS_TOOLS = [
    # ═══════════════════════════════════════
    #  Core Thinking Tool (Phase 1)
    # ═══════════════════════════════════════
    {
        "name": "think",
        "description": "MANDATORY before every deployment. Reason through the problem step by step.\n\nUse this to:\n- Classify the message (Type A-E)\n- Decompose tasks into subtasks\n- Identify which agent handles each subtask\n- Define success criteria for each step\n- Anticipate failures and plan recovery\n- Evaluate results after each tool call\n\nYour thinking is logged internally but NEVER shown to Abdullah.\n\nExample: think('Type C task. Need to create Outlook account. Steps: 1) deploy browser_agent to navigate signup.live.com and fill form, 2) verify with browser check for inbox URL, 3) save credentials to memory, 4) report via iMessage. Risk: CAPTCHA may appear — browser agent has solve_captcha. Backup: if Outlook fails, try ProtonMail.')",
        "input_schema": {
            "type": "object",
            "properties": {
                "thought": {"type": "string", "description": "Your detailed reasoning. Include: message classification, task decomposition, agent selection, success criteria, risk assessment, backup plans."}
            },
            "required": ["thought"]
        }
    },

    # ═══════════════════════════════════════
    #  Environmental Awareness (Phase 2)
    # ═══════════════════════════════════════
    {
        "name": "scan_environment",
        "description": "Scan the Mac environment BEFORE acting. Returns: running apps, Chrome tabs, current directory, network status, system info, deployment budget.\n\nUse at the START of every Type C task to:\n- See what's already running (Chrome open? Which tabs?)\n- Check internet connectivity\n- Know deployment budget remaining\n- Avoid blind deployments\n\nFor Type A/B messages, skip this — just respond.\n\nExample: scan_environment(['apps', 'tabs']) — quick check of what's open\nExample: scan_environment(['all']) — full system scan before complex task",
        "input_schema": {
            "type": "object",
            "properties": {
                "checks": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["apps", "tabs", "files", "network", "system", "all"]},
                    "description": "What to scan. 'all' for full scan, or pick specific: 'apps' (running apps), 'tabs' (Chrome tabs), 'files' (current dir), 'network' (internet check), 'system' (disk/battery/uptime).",
                    "default": ["all"]
                }
            },
            "required": []
        }
    },

    # ═══════════════════════════════════════
    #  Verification Loop (Phase 3)
    # ═══════════════════════════════════════
    {
        "name": "verify_result",
        "description": "MANDATORY after every agent deployment. Verify that the work ACTUALLY succeeded — don't trust agent claims.\n\nModes:\n- 'browser': Checks current Chrome page URL + visible text. Use after browser agent tasks.\n- 'command': Runs a shell command and checks output. Use after coder/system agent tasks.\n- 'file': Checks if a file/directory exists + preview. Use after file agent tasks.\n- 'process': Checks if a process is running. Use after launching apps/servers.\n\nExamples:\n  verify_result('browser', 'outlook', 'outlook.live.com') — checks if browser shows Outlook inbox\n  verify_result('command', 'cat ~/project/index.html', '<html>') — checks file was created correctly\n  verify_result('file', '~/project/package.json') — checks file exists\n  verify_result('process', 'node') — checks if Node.js is running\n\nIf verification FAILS, use the Smart Recovery Ladder — don't blindly retry.",
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["browser", "command", "file", "process"],
                    "description": "Verification mode."
                },
                "check": {
                    "type": "string",
                    "description": "What to check. browser: expected URL/text. command: shell command to run. file: file path. process: process name."
                },
                "expected": {
                    "type": "string",
                    "description": "Expected substring in the result. If found → VERIFIED. If not → FAILED. Omit for info-only checks."
                }
            },
            "required": ["type", "check"]
        }
    },

    # ═══════════════════════════════════════
    #  Checkpoint & Progress (Phase 8)
    # ═══════════════════════════════════════
    {
        "name": "checkpoint",
        "description": "Save progress so you can resume if interrupted. Use before risky operations.\n\nExample: checkpoint('Created outlook account, password saved', 'Still need to verify inbox access and save to memory')",
        "input_schema": {
            "type": "object",
            "properties": {
                "completed": {"type": "string", "description": "What's done so far (specific: URLs, files, accounts, etc.)"},
                "remaining": {"type": "string", "description": "What still needs to be done"}
            },
            "required": ["completed", "remaining"]
        }
    },

    # ═══════════════════════════════════════
    #  Agent Deployment
    # ═══════════════════════════════════════
    {
        "name": "deploy_browser_agent",
        "description": "Deploy Browser Agent for web tasks. Controls Chrome PHYSICALLY (real mouse + keyboard clicks).\n\nCapabilities: Navigate URLs, fill forms, click buttons, sign up for accounts, read page content, handle CAPTCHAs, manage tabs.\n\nCRITICAL — Give COMPLETE instructions:\n✅ GOOD: 'Go to https://signup.live.com. Fill the email field (#floatingLabelInput4) with tarsbot2026@outlook.com. Click Next. Wait 3 seconds. Fill the password field with MyP@ss2026!. Click Next. Fill first name with Tars, last name with Bot. Click Next. Select birth month January, day 1, year 1999. Click Next. If CAPTCHA appears, call solve_captcha(), wait 3s, look again. When you see the Outlook inbox or a welcome page, call done.'\n❌ BAD: 'Create an Outlook account'\n\nThe agent has NO context about your plan. Spell out EVERY step, EVERY value, EVERY click target.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "COMPLETE browser task with ALL details: exact URLs, exact values to type, exact buttons to click, CAPTCHA instructions, and what success looks like."}
            },
            "required": ["task"]
        }
    },
    {
        "name": "deploy_coder_agent",
        "description": "Deploy Coder Agent for software development.\n\nCapabilities: Write code (any language), build projects, debug, run tests, git ops, install packages, deploy.\n\nGive COMPLETE task:\n✅ GOOD: 'Create a Python Flask API at ~/projects/api/app.py. It should have 3 endpoints: GET /health returns {\"status\": \"ok\"}, POST /users accepts {\"name\", \"email\"} and saves to users.json, GET /users returns all users. Use Flask, add requirements.txt with flask. Run it on port 5000 and verify it responds to curl localhost:5000/health.'\n❌ BAD: 'Build me an API'",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "COMPLETE coding task: requirements, tech stack, file paths, expected behavior, test criteria."}
            },
            "required": ["task"]
        }
    },
    {
        "name": "deploy_system_agent",
        "description": "Deploy System Agent for macOS automation.\n\nCapabilities: Open/control apps, type text, press keyboard shortcuts, click at coordinates, take screenshots, run AppleScript, manage system settings.\n\nCANNOT browse the web — never send web tasks to this agent.\n\n✅ GOOD: 'Open System Settings, navigate to Wi-Fi, and check if connected. Take a screenshot to confirm.'\n❌ BAD: 'Go to google.com' — use browser agent for that",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "System task: app names, specific actions, keyboard shortcuts, expected result."}
            },
            "required": ["task"]
        }
    },
    {
        "name": "deploy_research_agent",
        "description": "Deploy Research Agent for information gathering.\n\nCapabilities: Google search, read web pages, extract specific info, cross-reference sources, compile findings.\n\nREAD-ONLY — cannot interact with websites (no clicking, no form filling, no signups).\nUse for finding info BEFORE deploying other agents.\n\n✅ GOOD: 'Research the cheapest flights from Tampa to NYC in March 2026. Check Google Flights, Kayak, and Skyscanner. Return: airline, price, dates, and booking URL for top 3 options.'\n❌ BAD: 'Book me a flight' — use browser agent for booking",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "Research question: what info to find, how many sources to check, what details needed."}
            },
            "required": ["task"]
        }
    },
    {
        "name": "deploy_file_agent",
        "description": "Deploy File Agent for file management.\n\nCapabilities: Find, organize, move, copy, delete, compress, extract files and directories.\n\n✅ GOOD: 'Organize ~/Desktop — move all .pdf files to ~/Documents/PDFs, all .png/.jpg to ~/Pictures/Screenshots, delete any .tmp files. Show a tree of ~/Desktop when done.'\n❌ BAD: 'Clean up my files'",
        "input_schema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "File task: paths, patterns, where to move things, what to clean up."}
            },
            "required": ["task"]
        }
    },

    # ═══════════════════════════════════════
    #  Communication
    # ═══════════════════════════════════════
    {
        "name": "send_imessage",
        "description": "Send an iMessage to Abdullah. This is your ONLY output channel — Abdullah NEVER sees your text responses.\n\nUse for:\n- Responding to conversations (Type A): Keep it short, punchy, TARS-style\n- Answering questions (Type B): Give the answer directly\n- Task acknowledgment (Type C): 'On it 🎯'\n- Progress updates: 'Step 2/4 done — created the account'\n- Final reports: '✅ Done. [specific results]'\n- Asking for help: Ask a SPECIFIC question, not 'what should I do?'\n\nNEVER say 'done' unless verify_result confirmed success.\nKeep messages concise — 1-3 sentences unless reporting detailed results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The iMessage to send. Be specific, concise, and TARS-style."}
            },
            "required": ["message"]
        }
    },
    {
        "name": "wait_for_reply",
        "description": "Wait for Abdullah to reply via iMessage. Blocks until reply received or timeout.\n\nUse after asking a question. Default timeout is 5 minutes.\n\nExample: After sending 'Which email provider — Outlook or Gmail?', call wait_for_reply(300) to wait up to 5 min.",
        "input_schema": {
            "type": "object",
            "properties": {
                "timeout": {"type": "integer", "description": "Max seconds to wait (default 300)", "default": 300}
            },
            "required": []
        }
    },

    # ═══════════════════════════════════════
    #  Memory (Phase 9)
    # ═══════════════════════════════════════
    {
        "name": "save_memory",
        "description": "Save information to persistent memory for future sessions.\n\nCategories:\n- 'credential': Login info (ALWAYS save after account creation)\n- 'preference': User likes/dislikes\n- 'project': Project details, tech stack, repo URLs\n- 'learned': Patterns that work/don't work (e.g., 'Outlook signup needs #floatingLabelInput4 for email')\n- 'context': Current state/task info\n- 'note': General notes\n\nExamples:\n  save_memory('credential', 'outlook_tarsbot', 'tarsbot2026@outlook.com / MyP@ss2026!')\n  save_memory('learned', 'outlook_signup_flow', 'Email field is #floatingLabelInput4, password step comes after clicking Next')\n  save_memory('preference', 'code_style', 'Abdullah prefers Python, dark themes, minimal comments')",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["preference", "project", "context", "note", "credential", "learned"]},
                "key": {"type": "string", "description": "Short label (e.g., 'outlook_account', 'project_tars_repo')"},
                "value": {"type": "string", "description": "Information to remember (include all relevant details)"}
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "recall_memory",
        "description": "Search persistent memory for information from past sessions.\n\nSearches: context, preferences, projects, credentials, learned patterns, and action history.\n\nALWAYS check memory before:\n- Starting a task that might relate to previous work\n- Creating accounts (might already exist)\n- Working on a project (might have saved context)\n\nExamples:\n  recall_memory('outlook account')\n  recall_memory('project tars')\n  recall_memory('flight preferences')",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for (keywords, not full sentences)"}
            },
            "required": ["query"]
        }
    },

    # ═══════════════════════════════════════
    #  Quick Tools
    # ═══════════════════════════════════════
    {
        "name": "run_quick_command",
        "description": "Run a quick shell command for fast checks. Returns stdout + stderr.\n\nGood for: ls, cat, grep, curl, ping, which, brew list, pip list, git status, df -h, uptime, whoami, date\nNOT for: complex multi-step operations (use deploy_coder_agent), long-running processes, interactive commands.\n\nExamples:\n  run_quick_command('curl -s wttr.in/Tampa?format=3') — weather\n  run_quick_command('git -C ~/projects/tars status') — git status\n  run_quick_command('pip list | grep flask') — check if flask installed",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run (non-interactive, short-running)"},
                "timeout": {"type": "integer", "description": "Timeout seconds (default 30)", "default": 30}
            },
            "required": ["command"]
        }
    },
    {
        "name": "quick_read_file",
        "description": "Read a file's contents quickly. Returns full text (truncated at 50KB).\n\nUse absolute paths. For large files, use run_quick_command with head/tail/grep instead.\n\nExamples:\n  quick_read_file('/Users/abdullah/Desktop/notes.txt')\n  quick_read_file('/Users/abdullah/Desktop/untitled folder/tars/config.yaml')",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute file path to read"}
            },
            "required": ["path"]
        }
    },

    # ═══════════════════════════════════════
    #  Direct Mac Control (brain-level, no agent needed)
    # ═══════════════════════════════════════
    {
        "name": "mac_mail",
        "description": "Quick email operations without deploying an agent. Actions:\n- 'unread' → get unread count\n- 'inbox' → read latest 5 emails\n- 'read' → read specific email by index\n- 'search' → search by keyword\n- 'send' → send an email\n\nExamples:\n  mac_mail('unread')\n  mac_mail('inbox', count=10)\n  mac_mail('send', to='bob@gmail.com', subject='Hi', body='Hello from TARS')",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["unread", "inbox", "read", "search", "send"]},
                "count": {"type": "integer", "description": "Emails to read (inbox action)", "default": 5},
                "index": {"type": "integer", "description": "Email index (read action)"},
                "keyword": {"type": "string", "description": "Search keyword (search action)"},
                "to": {"type": "string", "description": "Recipient (send action)"},
                "subject": {"type": "string", "description": "Subject (send action)"},
                "body": {"type": "string", "description": "Body (send action)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "mac_notes",
        "description": "Quick Apple Notes operations.\n- 'list' → list all notes\n- 'read' → read a note by name\n- 'create' → create a note\n- 'search' → search notes\n\nExamples:\n  mac_notes('list')\n  mac_notes('create', title='Shopping List', body='Milk, eggs, bread')",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "read", "create", "search"]},
                "note_name": {"type": "string", "description": "Note name (read action)"},
                "title": {"type": "string", "description": "Title (create action)"},
                "body": {"type": "string", "description": "Body (create action)"},
                "query": {"type": "string", "description": "Search query (search action)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "mac_calendar",
        "description": "Quick calendar operations.\n- 'events' → upcoming events\n- 'create' → create event\n\nExamples:\n  mac_calendar('events', days=14)\n  mac_calendar('create', title='Meeting', start='March 1, 2026 2:00 PM', end='March 1, 2026 3:00 PM')",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["events", "create"]},
                "days": {"type": "integer", "description": "Days ahead (events)", "default": 7},
                "calendar_name": {"type": "string", "description": "Calendar name"},
                "title": {"type": "string", "description": "Event title (create)"},
                "start": {"type": "string", "description": "Start date (create)"},
                "end": {"type": "string", "description": "End date (create)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "mac_reminders",
        "description": "Quick reminders operations.\n- 'list' → list reminders\n- 'create' → create reminder\n- 'complete' → complete reminder\n\nExamples:\n  mac_reminders('list')\n  mac_reminders('create', title='Buy milk', due='March 1, 2026')",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "create", "complete"]},
                "list_name": {"type": "string", "description": "Reminders list name"},
                "title": {"type": "string", "description": "Reminder title"},
                "due": {"type": "string", "description": "Due date (optional)"},
                "notes": {"type": "string", "description": "Notes (optional)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "mac_system",
        "description": "Quick system controls — no agent needed.\n- 'volume' → set volume (0-100)\n- 'dark_mode' → toggle dark mode\n- 'notify' → send notification\n- 'clipboard' → read clipboard\n- 'screenshot' → take screenshot\n- 'environment' → full Mac snapshot\n- 'battery' → battery status\n- 'spotlight' → search files\n\nExamples:\n  mac_system('volume', value=50)\n  mac_system('notify', message='Task complete!')\n  mac_system('environment')",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["volume", "dark_mode", "notify", "clipboard", "screenshot", "environment", "battery", "spotlight"]},
                "value": {"type": "integer", "description": "Volume level (volume action)"},
                "enabled": {"type": "boolean", "description": "Enable/disable (dark_mode action)"},
                "message": {"type": "string", "description": "Message (notify action)"},
                "query": {"type": "string", "description": "Search query (spotlight action)"}
            },
            "required": ["action"]
        }
    },
]
