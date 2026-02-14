"""
╔══════════════════════════════════════════╗
║      TARS — Memory Manager               ║
╚══════════════════════════════════════════╝

Persistent memory: context, preferences, project notes, history.
"""

import os
import json
from datetime import datetime


class MemoryManager:
    def __init__(self, config, base_dir):
        self.base_dir = base_dir
        self.context_file = os.path.join(base_dir, config["memory"]["context_file"])
        self.preferences_file = os.path.join(base_dir, config["memory"]["preferences_file"])
        self.history_file = os.path.join(base_dir, config["memory"]["history_file"])
        self.projects_dir = os.path.join(base_dir, config["memory"]["projects_dir"])
        self.max_history_context = config["memory"]["max_history_context"]

        # Ensure directories exist
        os.makedirs(os.path.dirname(self.context_file), exist_ok=True)
        os.makedirs(self.projects_dir, exist_ok=True)

        # Create default files if they don't exist
        self._init_files()

    def _init_files(self):
        if not os.path.exists(self.context_file):
            self._write(self.context_file, "# TARS — Current Context\n\n_No active task._\n")
        if not os.path.exists(self.preferences_file):
            self._write(self.preferences_file, "# TARS — Abdullah's Preferences\n\n_Learning..._\n")
        if not os.path.exists(self.history_file):
            self._write(self.history_file, "")

    def _write(self, path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _read(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    # ─── Context ─────────────────────────────────────

    def get_context_summary(self):
        """Get full memory context for the system prompt."""
        parts = []

        # Current context
        ctx = self._read(self.context_file)
        if ctx.strip():
            parts.append(f"### Current Context\n{ctx}")

        # Preferences
        prefs = self._read(self.preferences_file)
        if prefs.strip():
            parts.append(f"### Preferences\n{prefs}")

        # Recent history
        history = self._get_recent_history(10)
        if history:
            parts.append(f"### Recent Actions\n{history}")

        return "\n\n".join(parts) if parts else "_No memory yet._"

    def get_active_project(self):
        """Get the name of the active project from context."""
        ctx = self._read(self.context_file)
        for line in ctx.split("\n"):
            if "project" in line.lower() and ":" in line:
                return line.split(":", 1)[1].strip()
        return "None"

    def update_context(self, content):
        """Update the current context file."""
        self._write(self.context_file, content)

    # ─── Preferences ─────────────────────────────────

    def get_preferences(self):
        return self._read(self.preferences_file)

    def update_preferences(self, content):
        self._write(self.preferences_file, content)

    # ─── History ─────────────────────────────────────

    def log_action(self, action, input_data, result):
        """Append an action to the history log."""
        entry = {
            "ts": datetime.now().isoformat(),
            "action": action,
            "input": str(input_data)[:500],  # Truncate large inputs
            "result": str(result)[:500],
            "success": result.get("success", False) if isinstance(result, dict) else True,
        }
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _get_recent_history(self, n=10):
        """Get the last N actions from history."""
        try:
            with open(self.history_file, "r") as f:
                lines = f.readlines()
            recent = lines[-n:] if len(lines) > n else lines
            summaries = []
            for line in recent:
                try:
                    entry = json.loads(line)
                    status = "✅" if entry.get("success") else "❌"
                    summaries.append(f"{status} {entry['action']}: {entry['input'][:80]}")
                except json.JSONDecodeError:
                    continue
            return "\n".join(summaries)
        except FileNotFoundError:
            return ""

    # ─── Save/Recall (for Claude tool calls) ─────────

    def save(self, category, key, value):
        """Save a memory entry."""
        if category == "preference":
            prefs = self._read(self.preferences_file)
            prefs += f"\n- **{key}**: {value}"
            self._write(self.preferences_file, prefs)
        elif category == "project":
            project_file = os.path.join(self.projects_dir, f"{key}.md")
            self._write(project_file, f"# Project: {key}\n\n{value}\n")
        elif category == "context":
            self.update_context(f"# Current Context\n\n**{key}**: {value}\n")
        elif category == "note":
            self.log_action("note", key, {"success": True, "content": value})

        return {"success": True, "content": f"Saved to {category}: {key}"}

    def recall(self, query):
        """Search memory for relevant information."""
        results = []
        query_lower = query.lower()

        # Search context
        ctx = self._read(self.context_file)
        if query_lower in ctx.lower():
            results.append(f"[Context] {ctx[:500]}")

        # Search preferences
        prefs = self._read(self.preferences_file)
        if query_lower in prefs.lower():
            results.append(f"[Preferences] {prefs[:500]}")

        # Search project files
        if os.path.exists(self.projects_dir):
            for fname in os.listdir(self.projects_dir):
                content = self._read(os.path.join(self.projects_dir, fname))
                if query_lower in content.lower():
                    results.append(f"[Project: {fname}] {content[:500]}")

        # Search recent history
        try:
            with open(self.history_file, "r") as f:
                for line in f:
                    if query_lower in line.lower():
                        results.append(f"[History] {line.strip()[:200]}")
        except FileNotFoundError:
            pass

        if results:
            return {"success": True, "content": "\n\n".join(results[:10])}
        else:
            return {"success": True, "content": f"No memories found matching '{query}'"}
