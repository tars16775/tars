"""
╔══════════════════════════════════════════╗
║      TARS — Hands: Mac Controller        ║
╚══════════════════════════════════════════╝

Controls macOS via AppleScript/osascript.
Opens apps, types text, presses keys, clicks.
"""

import subprocess
import time


def _run_applescript(script):
    """Run an AppleScript and return the output."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return {"success": True, "content": result.stdout.strip()}
        else:
            return {"success": False, "error": True, "content": f"AppleScript error: {result.stderr.strip()}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": True, "content": "AppleScript timed out after 30s"}
    except Exception as e:
        return {"success": False, "error": True, "content": f"Error: {e}"}


def open_app(app_name):
    """Open a macOS application by name."""
    script = f'tell application "{app_name}" to activate'
    result = _run_applescript(script)
    if result["success"]:
        result["content"] = f"Opened {app_name}"
        time.sleep(1)  # Give app time to launch
    return result


def type_text(text):
    """Type text into the frontmost application."""
    # Escape special characters for AppleScript
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
    tell application "System Events"
        keystroke "{escaped}"
    end tell
    '''
    result = _run_applescript(script)
    if result["success"]:
        result["content"] = f"Typed {len(text)} characters"
    return result


def key_press(keys):
    """
    Press keyboard shortcut.
    Format: 'command+s', 'command+shift+p', 'return', 'tab', etc.
    """
    parts = keys.lower().split("+")
    key = parts[-1].strip()
    modifiers = [p.strip() for p in parts[:-1]] if len(parts) > 1 else []

    # Map key names to AppleScript key codes
    special_keys = {
        "return": "return", "enter": "return",
        "tab": "tab", "escape": "escape",
        "space": "space", "delete": "delete",
        "up": "up arrow", "down": "down arrow",
        "left": "left arrow", "right": "right arrow",
    }

    # Build modifier string
    modifier_map = {
        "command": "command down",
        "cmd": "command down",
        "control": "control down",
        "ctrl": "control down",
        "option": "option down",
        "alt": "option down",
        "shift": "shift down",
    }

    modifier_str = ", ".join(modifier_map.get(m, f"{m} down") for m in modifiers)

    if key in special_keys:
        if modifier_str:
            script = f'''
            tell application "System Events"
                key code {_key_code(special_keys[key])} using {{{modifier_str}}}
            end tell
            '''
        else:
            script = f'''
            tell application "System Events"
                key code {_key_code(special_keys[key])}
            end tell
            '''
    else:
        if modifier_str:
            script = f'''
            tell application "System Events"
                keystroke "{key}" using {{{modifier_str}}}
            end tell
            '''
        else:
            script = f'''
            tell application "System Events"
                keystroke "{key}"
            end tell
            '''

    result = _run_applescript(script)
    if result["success"]:
        result["content"] = f"Pressed {keys}"
    return result


def _key_code(key_name):
    """Map key names to macOS key codes."""
    codes = {
        "return": 36, "tab": 48, "space": 49, "delete": 51,
        "escape": 53, "up arrow": 126, "down arrow": 125,
        "left arrow": 123, "right arrow": 124,
    }
    return codes.get(key_name, 36)


def click(x, y, double_click=False):
    """Click at screen coordinates."""
    click_cmd = "click" if not double_click else "double click"
    script = f'''
    tell application "System Events"
        {click_cmd} at {{{x}, {y}}}
    end tell
    '''
    # Use cliclick if available (more reliable), fallback to AppleScript
    try:
        flag = "-d" if double_click else ""
        cmd = f"cliclick {flag} c:{x},{y}"
        result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return {"success": True, "content": f"Clicked at ({x}, {y})"}
    except FileNotFoundError:
        pass  # cliclick not installed, use AppleScript

    result = _run_applescript(script)
    if result["success"]:
        result["content"] = f"Clicked at ({x}, {y})"
    return result


def get_frontmost_app():
    """Get the name of the frontmost application."""
    script = 'tell application "System Events" to get name of first process whose frontmost is true'
    return _run_applescript(script)


def take_screenshot():
    """Take a screenshot and save it to a temp location."""
    import tempfile
    import os
    path = os.path.join(tempfile.gettempdir(), f"tars_screenshot_{int(time.time())}.png")
    try:
        subprocess.run(["screencapture", "-x", path], timeout=10)
        return {"success": True, "content": f"Screenshot saved to {path}"}
    except Exception as e:
        return {"success": False, "error": True, "content": f"Screenshot failed: {e}"}
