"""
╔══════════════════════════════════════════╗
║       TARS — Utilities: Safety           ║
╚══════════════════════════════════════════╝

Guardrails, destructive action detection, kill switch.
"""

import re

# Patterns that indicate destructive actions
DESTRUCTIVE_PATTERNS = [
    r"rm\s+(-rf?|--recursive)",
    r"rmdir",
    r"git\s+push\s+.*--force",
    r"git\s+push\s+-f",
    r"git\s+reset\s+--hard",
    r"DROP\s+TABLE",
    r"DELETE\s+FROM",
    r"format\s+",
    r"mkfs\.",
    r"dd\s+if=",
    r">\s*/dev/",
    r"chmod\s+777",
    r"sudo\s+rm",
]


def is_destructive(command):
    """Check if a shell command looks destructive."""
    for pattern in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def is_path_allowed(path, allowed_paths):
    """Check if a file path is within allowed paths. Empty = all allowed."""
    if not allowed_paths:
        return True
    import os
    path = os.path.abspath(os.path.expanduser(path))
    for allowed in allowed_paths:
        allowed = os.path.abspath(os.path.expanduser(allowed))
        if path.startswith(allowed):
            return True
    return False
