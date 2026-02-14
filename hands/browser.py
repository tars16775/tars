"""
╔══════════════════════════════════════════════════════════════╗
║          TARS — Browser: Physical Interaction Engine          ║
╠══════════════════════════════════════════════════════════════╣
║  Philosophy: JS is for READING. Physical mouse + keyboard    ║
║  for ALL ACTIONS. Exactly how a human uses a browser.        ║
║                                                              ║
║  Phase 1:  Physical primitives (cliclick, System Events)     ║
║  Phase 2:  Chrome window management (activate, bounds)       ║
║  Phase 3:  JS read-only helpers (text, DOM inspection)       ║
║  Phase 4:  Dynamic coordinate mapping (any window size)      ║
║  Phase 5:  Smart click (find element → coords → click)      ║
║  Phase 6:  Smart type (click field → physical keyboard)      ║
║  Phase 7:  Dropdown handling (click open → find → click)     ║
║  Phase 8:  Form intelligence (detect fields, tab order)      ║
║  Phase 9:  Page state detection (loading, transitions)       ║
║  Phase 10: Scroll intelligence (find offscreen elements)     ║
║  Phase 11: Screenshot capture (visual verification)          ║
║  Phase 12: Navigation (back, forward, tabs, URLs)            ║
║  Phase 13: Waiting strategies (smart dynamic waits)          ║
║  Phase 14: Error recovery (retry with different approach)    ║
║  Phase 15: File upload/download detection                    ║
║  Phase 16: Popup/alert handling                              ║
║  Phase 17: Google search helper                              ║
║  Phase 18: Multi-tab orchestration                           ║
║  Phase 19: Challenge/CAPTCHA detection                       ║
║  Phase 20: Full integration + public API for agent           ║
╚══════════════════════════════════════════════════════════════╝
"""

import subprocess
import time
import json
import urllib.parse
import os
import tempfile


# ═══════════════════════════════════════════════════════
#  PHASE 1: Physical Primitives
# ═══════════════════════════════════════════════════════

def _applescript(script):
    """Run AppleScript, return stdout string or empty on error."""
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else ""
    except:
        return ""


def _physical_click(x, y):
    """Physical mouse click at screen coordinates using cliclick."""
    subprocess.run(["cliclick", f"c:{x},{y}"], capture_output=True, timeout=5)
    time.sleep(0.15)


def _physical_double_click(x, y):
    """Physical double-click at screen coordinates."""
    subprocess.run(["cliclick", f"dc:{x},{y}"], capture_output=True, timeout=5)
    time.sleep(0.15)


def _physical_move(x, y):
    """Move mouse to coordinates without clicking."""
    subprocess.run(["cliclick", f"m:{x},{y}"], capture_output=True, timeout=5)


def _physical_type(text):
    """Type text with physical keyboard via System Events. Handles any character."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    _applescript(f'''
        tell application "System Events"
            keystroke "{escaped}"
        end tell
    ''')
    time.sleep(0.1)


def _physical_key(key_name):
    """Press a special key physically (return, tab, escape, arrows, etc.)."""
    codes = {
        "return": 36, "enter": 36, "tab": 48, "space": 49,
        "delete": 51, "backspace": 51, "escape": 53, "esc": 53,
        "up": 126, "down": 125, "left": 123, "right": 124,
        "f5": 96, "home": 115, "end": 119, "pageup": 116, "pagedown": 121,
    }
    code = codes.get(key_name.lower())
    if code is not None:
        _applescript(f'''
            tell application "System Events"
                key code {code}
            end tell
        ''')
    else:
        # Try as single character keystroke
        _physical_type(key_name)
    time.sleep(0.1)


def _physical_hotkey(modifiers, key):
    """Press a keyboard shortcut (e.g. command+a, command+shift+t)."""
    mod_map = {
        "command": "command down", "cmd": "command down",
        "control": "control down", "ctrl": "control down",
        "option": "option down", "alt": "option down",
        "shift": "shift down",
    }
    mod_str = ", ".join(mod_map.get(m, f"{m} down") for m in modifiers)
    _applescript(f'''
        tell application "System Events"
            keystroke "{key}" using {{{mod_str}}}
        end tell
    ''')
    time.sleep(0.15)


def _select_all_and_delete():
    """Select all text in current field and delete it."""
    _physical_hotkey(["command"], "a")
    time.sleep(0.05)
    _physical_key("delete")
    time.sleep(0.05)


# ═══════════════════════════════════════════════════════
#  PHASE 2: Chrome Window Management
# ═══════════════════════════════════════════════════════

def _activate_chrome():
    """Bring Chrome to front, ensure a window exists."""
    _applescript('''
        tell application "Google Chrome"
            activate
            if (count of windows) = 0 then make new window
        end tell
    ''')
    time.sleep(0.3)


def _chrome_bounds():
    """Get Chrome window bounds as (x, y, w, h) in screen coords."""
    raw = _applescript('''
        tell application "Google Chrome"
            set b to bounds of first window
            return (item 1 of b as text) & "," & (item 2 of b as text) & "," & (item 3 of b as text) & "," & (item 4 of b as text)
        end tell
    ''')
    if not raw:
        return (0, 30, 1920, 997)  # Fallback
    parts = [int(p) for p in raw.split(",")]
    return (parts[0], parts[1], parts[2] - parts[0], parts[3] - parts[1])


# ═══════════════════════════════════════════════════════
#  PHASE 3: JS Read-Only Helpers (NEVER use JS to act)
# ═══════════════════════════════════════════════════════

def _js(code):
    """Execute JavaScript in Chrome's active tab. READ-ONLY usage.
    
    Uses IIFE wrapper. Returns string result.
    For page reading ONLY — never use JS to click, type, or modify DOM.
    """
    wrapped = (
        "(function(){"
        "try{"
        "var __r=(function(){" + code + "})();"
        "return (__r===undefined||__r===null)?'':String(__r);"
        "}catch(e){return 'JS_ERROR: '+e.message;}"
        "})()"
    )
    escaped = wrapped.replace("\\", "\\\\").replace('"', '\\"')
    result = _applescript(f'''
        tell application "Google Chrome"
            tell active tab of first window
                execute javascript "{escaped}"
            end tell
        end tell
    ''')
    return result if result and result != "missing value" else ""


def _js_raw(code):
    """Execute raw JS via AppleScript (no IIFE). For simple document property reads."""
    result = _applescript(f'''
        tell application "Google Chrome"
            tell active tab of first window
                set t to execute javascript "{code}"
            end tell
            return t
        end tell
    ''')
    return result if result and result != "missing value" else ""


# ═══════════════════════════════════════════════════════
#  PHASE 4: Dynamic Coordinate Mapping
# ═══════════════════════════════════════════════════════

def _viewport_info():
    """Get Chrome viewport info for coordinate mapping. Called dynamically every time."""
    raw = _js("""
        return JSON.stringify({
            sx: window.screenX,
            sy: window.screenY,
            oh: window.outerHeight,
            ih: window.innerHeight,
            ow: window.outerWidth,
            iw: window.innerWidth
        });
    """)
    try:
        info = json.loads(raw)
        return info
    except:
        # Fallback: calculate from Chrome bounds
        bx, by, bw, bh = _chrome_bounds()
        return {"sx": bx, "sy": by, "oh": bh, "ih": bh - 87, "ow": bw, "iw": bw}


def _viewport_to_screen(vx, vy):
    """Convert viewport coordinates (from getBoundingClientRect) to screen coordinates.
    
    Dynamically reads Chrome's current window position and toolbar height.
    Works with ANY window size, position, or monitor setup.
    """
    info = _viewport_info()
    toolbar_h = info["oh"] - info["ih"]
    screen_x = info["sx"] + vx
    screen_y = info["sy"] + toolbar_h + vy
    return (int(screen_x), int(screen_y))


def _element_center(selector):
    """Get the screen coordinates of an element's center. Returns (x, y) or None."""
    raw = _js(f"""
        var el = document.querySelector('{selector}');
        if (!el) return '';
        var r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) return '';
        return JSON.stringify({{x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), w: Math.round(r.width), h: Math.round(r.height)}});
    """)
    if not raw:
        return None
    try:
        pos = json.loads(raw)
        sx, sy = _viewport_to_screen(pos["x"], pos["y"])
        return (sx, sy)
    except:
        return None


def _element_center_by_text(text, tag_filter="button, a, [role=button], input[type=submit], span, div, label, li, [role=option], [role=menuitem], [role=link], [role=tab], p"):
    """Find an element by its visible text content and return screen coordinates.
    
    Does exact match first, then substring match. Returns (x, y) or None.
    """
    safe = text.replace("\\", "\\\\").replace("'", "\\'")
    raw = _js(f"""
        var els = document.querySelectorAll('{tag_filter}');
        var best = null;
        // Exact match first
        for (var i = 0; i < els.length; i++) {{
            var t = (els[i].innerText||els[i].value||'').trim();
            var r = els[i].getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            if (t === '{safe}') {{ best = els[i]; break; }}
        }}
        // Substring match if no exact
        if (!best) {{
            for (var i = 0; i < els.length; i++) {{
                var t = (els[i].innerText||els[i].value||'').trim();
                var r = els[i].getBoundingClientRect();
                if (r.width === 0 || r.height === 0) continue;
                if (t.indexOf('{safe}') !== -1 && t.length < 100) {{ best = els[i]; break; }}
            }}
        }}
        if (!best) return '';
        var r = best.getBoundingClientRect();
        return JSON.stringify({{x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)}});
    """)
    if not raw:
        return None
    try:
        pos = json.loads(raw)
        sx, sy = _viewport_to_screen(pos["x"], pos["y"])
        return (sx, sy)
    except:
        return None


# ═══════════════════════════════════════════════════════
#  PHASE 5: Smart Click
# ═══════════════════════════════════════════════════════

def act_click(target):
    """Click an element by visible text OR CSS selector. Uses physical mouse.
    
    - If target starts with # . [ → treat as CSS selector
    - Otherwise → find by visible text
    Returns description string.
    """
    is_css = len(target) > 0 and target[0] in ("#", ".", "[")

    if is_css:
        coords = _element_center(target)
        if not coords:
            return f"ERROR: No visible element found for selector: {target}"
        _physical_click(coords[0], coords[1])
        return f"Clicked element at ({coords[0]}, {coords[1]}) via selector: {target}"
    else:
        coords = _element_center_by_text(target)
        if not coords:
            return f"ERROR: No visible element with text: {target}"
        _physical_click(coords[0], coords[1])
        return f"Clicked '{target}' at ({coords[0]}, {coords[1]})"


# ═══════════════════════════════════════════════════════
#  PHASE 6: Smart Type
# ═══════════════════════════════════════════════════════

def act_fill(selector, value):
    """Click on a field, clear it, and type a value physically.
    
    This is exactly how a human fills a form:
    1. Click the field (physical mouse)
    2. Select all (Cmd+A)
    3. Type the new value (physical keyboard)
    """
    coords = _element_center(selector)
    if not coords:
        return f"ERROR: No visible field for: {selector}"

    # Click the field
    _physical_click(coords[0], coords[1])
    time.sleep(0.2)

    # Select all existing text and delete
    _select_all_and_delete()
    time.sleep(0.1)

    # Type the value character by character for reliability
    _physical_type(value)
    time.sleep(0.1)

    return f"Filled {selector} with '{value}'"


# ═══════════════════════════════════════════════════════
#  PHASE 7: Dropdown Handling
# ═══════════════════════════════════════════════════════

def act_select_option(dropdown_text_or_selector, option_text):
    """Handle ANY dropdown — standard <select> or custom Material/Google.
    
    Strategy (like a human):
    1. Click on the dropdown to open it
    2. Wait for options to appear
    3. Find the option by text
    4. Click on it physically
    
    Works with any dropdown framework because it uses physical clicks.
    """
    # Step 1: Click the dropdown to open it
    is_css = len(dropdown_text_or_selector) > 0 and dropdown_text_or_selector[0] in ("#", ".", "[")
    
    if is_css:
        coords = _element_center(dropdown_text_or_selector)
    else:
        coords = _element_center_by_text(dropdown_text_or_selector)

    if not coords:
        return f"ERROR: Dropdown not found: {dropdown_text_or_selector}"

    _physical_click(coords[0], coords[1])
    time.sleep(0.8)  # Wait for dropdown to open

    # Step 2: Find and click the option
    # Search across common dropdown option patterns
    safe = option_text.replace("\\", "\\\\").replace("'", "\\'")
    raw = _js(f"""
        // Look for visible option elements in open dropdown/popup
        var selectors = [
            '[role=option]', '[role=menuitem]', '[role=listbox] li',
            'li', 'option', '[data-value]', '.MuiMenuItem-root',
            'ul li', 'div[role=listbox] div', 'select option'
        ];
        var all = [];
        selectors.forEach(function(s) {{
            document.querySelectorAll(s).forEach(function(el) {{ all.push(el); }});
        }});
        // Also check for standard <select> that might have opened
        var openSelect = document.querySelector('select:focus');
        if (openSelect) {{
            for (var i = 0; i < openSelect.options.length; i++) {{
                if (openSelect.options[i].text.trim() === '{safe}') {{
                    return JSON.stringify({{native: true, index: i, selector: openSelect.id ? '#' + openSelect.id : 'select'}});
                }}
            }}
        }}
        // Find in custom dropdown options
        for (var i = 0; i < all.length; i++) {{
            var t = all[i].textContent.trim();
            var r = all[i].getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            if (t === '{safe}') {{
                return JSON.stringify({{x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)}});
            }}
        }}
        // Substring match
        for (var i = 0; i < all.length; i++) {{
            var t = all[i].textContent.trim();
            var r = all[i].getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            if (t.indexOf('{safe}') !== -1 && t.length < 60) {{
                return JSON.stringify({{x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)}});
            }}
        }}
        // List what IS visible for debugging
        var visible = [];
        all.forEach(function(el) {{
            var r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0 && el.textContent.trim()) visible.push(el.textContent.trim().substring(0,30));
        }});
        return JSON.stringify({{error: true, visible: visible.slice(0,15)}});
    """)

    if not raw:
        return f"ERROR: No options appeared after clicking dropdown"

    try:
        data = json.loads(raw)
    except:
        return f"ERROR: Bad option data: {raw[:100]}"

    # Handle native <select>
    if data.get("native"):
        _js(f"""
            var sel = document.querySelector('{data["selector"]}');
            sel.selectedIndex = {data["index"]};
            sel.dispatchEvent(new Event('change', {{bubbles:true}}));
        """)
        return f"Selected '{option_text}' from native dropdown"

    # Handle error
    if data.get("error"):
        visible = ", ".join(data.get("visible", []))
        return f"ERROR: Option '{option_text}' not found. Visible options: {visible}"

    # Physical click the option
    sx, sy = _viewport_to_screen(data["x"], data["y"])
    _physical_click(sx, sy)
    time.sleep(0.3)

    return f"Selected '{option_text}'"


# ═══════════════════════════════════════════════════════
#  PHASE 8: Form Intelligence (inspect_page)
# ═══════════════════════════════════════════════════════

def act_inspect_page():
    """Get a structured view of all VISIBLE interactive elements on the page.
    
    Returns: text fields, dropdowns, buttons, links, checkboxes.
    Only visible elements (no display:none or zero-size).
    The agent uses this output to decide what to click/fill.
    """
    result = _js("""
        function isVis(el) {
            if (!el) return false;
            var s = window.getComputedStyle(el);
            if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false;
            var r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        }
        var out = [];
        
        // Page heading
        var h = document.querySelector('h1,h2');
        var ht = h && isVis(h) ? h.innerText.trim().substring(0,80) : document.title;
        out.push('PAGE: ' + ht);
        out.push('URL: ' + location.href);
        out.push('');
        
        // Input fields
        var inputs = document.querySelectorAll('input:not([type=hidden]), textarea');
        var vis = [];
        inputs.forEach(function(el) { if (isVis(el)) vis.push(el); });
        if (vis.length) {
            out.push('FIELDS:');
            vis.forEach(function(el) {
                var label = '';
                if (el.id) { var l = document.querySelector('label[for=\"'+el.id+'\"]'); if (l) label = l.innerText.trim(); }
                if (!label) label = el.getAttribute('aria-label') || el.placeholder || el.name || '';
                var sel = el.id ? '#'+el.id : (el.name ? '[name='+el.name+']' : '');
                var val = el.value ? ' = \"'+el.value.substring(0,30)+'\"' : '';
                var typ = el.type || 'text';
                out.push('  ['+typ+'] '+label+' → '+sel+val);
            });
            out.push('');
        }
        
        // Standard <select> dropdowns
        var sels = document.querySelectorAll('select');
        var visSel = [];
        sels.forEach(function(el) { if (isVis(el) || (el.parentElement && isVis(el.parentElement))) visSel.push(el); });
        if (visSel.length) {
            out.push('DROPDOWNS:');
            visSel.forEach(function(el) {
                var label = '';
                if (el.id) { var l = document.querySelector('label[for=\"'+el.id+'\"]'); if (l) label = l.innerText.trim(); }
                if (!label) label = el.name || el.id || '?';
                var sel = el.id ? '#'+el.id : (el.name ? 'select[name='+el.name+']' : 'select');
                var cur = el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : '';
                var opts = Array.from(el.options).map(function(o){return o.text.trim();}).filter(function(t){return t;}).slice(0,12).join(', ');
                out.push('  '+label+' → '+sel+' (current: '+cur+') options: '+opts);
            });
            out.push('');
        }
        
        // Custom dropdowns (role=listbox, role=combobox, or div wrapping a hidden select)
        var customs = [];
        document.querySelectorAll('[role=listbox], [role=combobox]').forEach(function(el) { if (isVis(el)) customs.push(el); });
        // Also find parent divs that wrap hidden selects
        document.querySelectorAll('div > select').forEach(function(sel) {
            var p = sel.parentElement;
            if (p && isVis(p) && p.id) {
                var already = customs.some(function(c) { return c === p || p.contains(c) || c.contains(p); });
                if (!already) customs.push(p);
            }
        });
        if (customs.length) {
            out.push('CUSTOM DROPDOWNS:');
            customs.forEach(function(el) {
                var cid = el.id || (el.closest('[id]') || {}).id || '?';
                var label = el.getAttribute('aria-label') || '';
                if (!label) {
                    var lbl = el.getAttribute('aria-labelledby');
                    if (lbl) { lbl.split(' ').forEach(function(id) { var e = document.getElementById(id); if (e) label += e.innerText.trim() + ' '; }); }
                }
                if (!label) {
                    var spans = (el.closest('[id]') || el).querySelectorAll('label, span');
                    spans.forEach(function(s) { if (!label && s.innerText.trim().length < 30) label = s.innerText.trim(); });
                }
                var cur = el.innerText.trim().substring(0,30) || '(empty)';
                // Check for hidden options
                var innerSel = (el.closest('[id]') || el).querySelector('select');
                var optStr = '';
                if (innerSel) optStr = ' options: ' + Array.from(innerSel.options).slice(0,12).map(function(o){return o.text.trim();}).filter(function(t){return t;}).join(', ');
                out.push('  '+(label||cid)+' → click text: \"'+(label||cid)+'\" or id: #'+cid+optStr+' (showing: '+cur+')');
            });
            out.push('');
        }
        
        // Checkboxes
        var checks = document.querySelectorAll('input[type=checkbox]');
        var visCheck = [];
        checks.forEach(function(el) { if (isVis(el)) visCheck.push(el); });
        if (visCheck.length) {
            out.push('CHECKBOXES:');
            visCheck.forEach(function(el) {
                var lbl = el.closest('label');
                var txt = lbl ? lbl.innerText.trim().substring(0,60) : (el.name || el.id || '?');
                var sel = el.id ? '#'+el.id : (el.name ? '[name='+el.name+']' : '');
                out.push('  '+txt+' → '+sel+' ['+(el.checked?'checked':'unchecked')+']');
            });
            out.push('');
        }
        
        // Buttons
        var btns = document.querySelectorAll('button, input[type=submit], [role=button]');
        var visBtns = [];
        btns.forEach(function(el) { if (isVis(el) && (el.innerText||el.value||'').trim()) visBtns.push(el); });
        if (visBtns.length) {
            out.push('BUTTONS:');
            visBtns.forEach(function(el) {
                out.push('  ['+((el.innerText||el.value||'').trim().substring(0,50))+']');
            });
            out.push('');
        }
        
        // Links (first 10 visible)
        var links = [];
        document.querySelectorAll('a[href]').forEach(function(a) {
            if (links.length < 10 && isVis(a) && a.innerText.trim()) links.push(a);
        });
        if (links.length) {
            out.push('LINKS:');
            links.forEach(function(a) { out.push('  '+a.innerText.trim().substring(0,50)+' → '+a.href); });
        }
        
        return out.join('\\n');
    """)
    return result or "Could not inspect page (Chrome may not be active)"


# ═══════════════════════════════════════════════════════
#  PHASE 9: Page State Detection
# ═══════════════════════════════════════════════════════

def _page_ready():
    """Check if page is done loading."""
    state = _js("return document.readyState;")
    return state in ("complete", "interactive")


def _wait_for_page(max_seconds=12):
    """Wait for page to finish loading."""
    for _ in range(max_seconds * 4):
        if _page_ready():
            time.sleep(0.3)
            return True
        time.sleep(0.25)
    return False


def _page_changed(old_url="", old_title=""):
    """Check if the page has changed (URL or title or visible content shift)."""
    url = _js("return location.href;")
    title = _js("return document.title;")
    if url != old_url or title != old_title:
        return True
    return False


# ═══════════════════════════════════════════════════════
#  PHASE 10: Scroll Intelligence
# ═══════════════════════════════════════════════════════

def act_scroll(direction="down"):
    """Scroll the page physically using keyboard shortcuts.
    
    Uses physical Page Down/Up or Cmd+arrow for top/bottom.
    """
    _activate_chrome()
    if direction == "down":
        _physical_key("pagedown")
    elif direction == "up":
        _physical_key("pageup")
    elif direction == "top":
        _physical_hotkey(["command"], "up")
    elif direction == "bottom":
        _physical_hotkey(["command"], "down")
    time.sleep(0.3)
    return f"Scrolled {direction}"


def _scroll_to_element(selector):
    """Scroll an element into view using JS (read operation — just changes scroll position)."""
    _js(f"""
        var el = document.querySelector('{selector}');
        if (el) el.scrollIntoView({{block:'center', behavior:'smooth'}});
    """)
    time.sleep(0.5)


# ═══════════════════════════════════════════════════════
#  PHASE 11: Screenshot Capture
# ═══════════════════════════════════════════════════════

def act_screenshot():
    """Take a screenshot. Returns the file path."""
    path = os.path.join(tempfile.gettempdir(), f"tars_browser_{int(time.time())}.png")
    subprocess.run(["screencapture", "-x", path], timeout=10)
    return f"Screenshot saved: {path}"


# ═══════════════════════════════════════════════════════
#  PHASE 12: Navigation
# ═══════════════════════════════════════════════════════

def act_goto(url):
    """Open a URL in a new Chrome tab."""
    _activate_chrome()
    _applescript(f'''
        tell application "Google Chrome"
            tell first window to make new tab with properties {{URL:"{url}"}}
        end tell
    ''')
    time.sleep(2)
    _wait_for_page()
    title = _js("return document.title;")
    return f"Opened {url} — {title}"


def act_read_page():
    """Read all visible text on the page."""
    text = _js_raw("document.body.innerText.substring(0, 12000)")
    if not text:
        return "(empty page or Chrome not open)"
    return text


def act_read_url():
    """Get current URL and title."""
    url = _js("return location.href;")
    title = _js("return document.title;")
    return f"URL: {url}\nTitle: {title}"


def act_back():
    """Navigate back using keyboard shortcut."""
    _activate_chrome()
    _physical_hotkey(["command"], "[")
    time.sleep(1.5)
    _wait_for_page()
    return f"Back → {_js('return document.title;')}"


def act_forward():
    """Navigate forward."""
    _activate_chrome()
    _physical_hotkey(["command"], "]")
    time.sleep(1.5)
    _wait_for_page()
    return f"Forward → {_js('return document.title;')}"


def act_refresh():
    """Refresh page."""
    _activate_chrome()
    _physical_hotkey(["command"], "r")
    time.sleep(2)
    _wait_for_page()
    return f"Refreshed → {_js('return document.title;')}"


def act_get_tabs():
    """List all Chrome tabs."""
    raw = _applescript('''
        tell application "Google Chrome"
            set out to ""
            repeat with w from 1 to (count of windows)
                repeat with t from 1 to (count of tabs of window w)
                    set out to out & t & ". " & title of tab t of window w & linefeed
                end repeat
            end repeat
            return out
        end tell
    ''')
    return raw or "No tabs"


def act_switch_tab(tab_number):
    """Switch to a tab by number."""
    _applescript(f'tell application "Google Chrome" to set active tab index of first window to {tab_number}')
    time.sleep(0.5)
    return f"Switched to tab {tab_number}: {_js('return document.title;')}"


def act_close_tab():
    """Close current tab."""
    _activate_chrome()
    _physical_hotkey(["command"], "w")
    time.sleep(0.5)
    return "Tab closed"


def act_new_tab(url=""):
    """Open a new tab, optionally with a URL."""
    _activate_chrome()
    if url:
        return act_goto(url)
    else:
        _physical_hotkey(["command"], "t")
        time.sleep(0.5)
        return "New empty tab opened"


# ═══════════════════════════════════════════════════════
#  PHASE 13: Smart Waiting
# ═══════════════════════════════════════════════════════

def act_wait(seconds=2):
    """Wait for N seconds."""
    time.sleep(int(seconds))
    return f"Waited {seconds}s"


def act_wait_for_text(text, timeout=10):
    """Wait for specific text to appear on the page."""
    safe = text.replace("\\", "\\\\").replace("'", "\\'")
    for _ in range(timeout * 2):
        found = _js(f"return document.body.innerText.indexOf('{safe}') !== -1 ? 'yes' : 'no';")
        if found == "yes":
            return f"Text '{text}' found on page"
        time.sleep(0.5)
    return f"Text '{text}' NOT found after {timeout}s"


# ═══════════════════════════════════════════════════════
#  PHASE 14: Error Recovery Helpers
# ═══════════════════════════════════════════════════════

def _try_click_approaches(target):
    """Try multiple approaches to click an element. Used as fallback."""
    # Approach 1: By text
    coords = _element_center_by_text(target)
    if coords:
        _physical_click(coords[0], coords[1])
        return f"Clicked '{target}' (by text)"

    # Approach 2: By CSS selector
    coords = _element_center(target)
    if coords:
        _physical_click(coords[0], coords[1])
        return f"Clicked '{target}' (by selector)"

    # Approach 3: Try aria-label
    coords = _element_center(f"[aria-label='{target}']")
    if coords:
        _physical_click(coords[0], coords[1])
        return f"Clicked '{target}' (by aria-label)"

    return None


# ═══════════════════════════════════════════════════════
#  PHASE 15: File Upload Detection
# ═══════════════════════════════════════════════════════

def _detect_file_input():
    """Check if there's a file upload input on the page."""
    result = _js("""
        var fi = document.querySelector('input[type=file]');
        return fi ? 'yes' : 'no';
    """)
    return result == "yes"


# ═══════════════════════════════════════════════════════
#  PHASE 16: Popup/Alert Handling
# ═══════════════════════════════════════════════════════

def act_handle_dialog(action="accept"):
    """Handle browser alert/confirm/prompt dialogs."""
    _js(f"""
        window.__tarsDialogResult = null;
        window.alert = function() {{ window.__tarsDialogResult = 'dismissed'; }};
        window.confirm = function() {{ window.__tarsDialogResult = 'confirmed'; return {'true' if action == 'accept' else 'false'}; }};
        window.prompt = function(msg) {{ window.__tarsDialogResult = 'prompted'; return {'null' if action == 'dismiss' else "'ok'"}; }};
    """)
    return f"Dialog handler set to {action}"


# ═══════════════════════════════════════════════════════
#  PHASE 17: Google Search Helper
# ═══════════════════════════════════════════════════════

def act_google(query):
    """Quick Google search: navigate, return results text."""
    encoded = urllib.parse.quote_plus(query)
    act_goto(f"https://www.google.com/search?q={encoded}")
    time.sleep(1.5)
    text = act_read_page()
    return f"Google results for '{query}':\n\n{text[:6000]}"


# ═══════════════════════════════════════════════════════
#  PHASE 18: Multi-Tab Orchestration
# ═══════════════════════════════════════════════════════

def act_tab_count():
    """Get the number of open tabs."""
    raw = _applescript('tell application "Google Chrome" to return count of tabs of first window')
    return f"Open tabs: {raw}"


# ═══════════════════════════════════════════════════════
#  PHASE 19: Challenge/CAPTCHA Detection
# ═══════════════════════════════════════════════════════

def _detect_challenge():
    """Detect if the page is BLOCKED by a CAPTCHA or verification challenge.
    
    Only returns true when a CAPTCHA is actually blocking the user, not when
    reCAPTCHA scripts/iframes are loaded in the background (which is normal
    on most Google pages).
    """
    text = _js("""
        var body = document.body.innerText;
        var lower = body.toLowerCase();
        var title = document.title.toLowerCase();
        
        // Only trigger on pages that are ENTIRELY a challenge (blocking page)
        // Google's "unusual traffic" full-page block
        if (title.indexOf('unusual traffic') !== -1) return 'Blocked: unusual traffic';
        if (title.indexOf('captcha') !== -1) return 'Blocked: CAPTCHA page';
        
        // Page body is very short AND mentions verification = likely a blocking challenge
        if (body.length < 1500) {
            if (lower.indexOf('verify you are human') !== -1) return 'Blocked: human verification';
            if (lower.indexOf('unusual traffic') !== -1) return 'Blocked: traffic challenge';
            if (lower.indexOf('are you a robot') !== -1) return 'Blocked: robot check';
            if (lower.indexOf('complete the security check') !== -1) return 'Blocked: security check';
        }
        
        // Visible reCAPTCHA challenge box (not background iframe)
        var visible = document.querySelector('.g-recaptcha, #recaptcha, [data-sitekey]');
        if (visible) {
            var r = visible.getBoundingClientRect();
            if (r.width > 50 && r.height > 50) return 'Visible CAPTCHA widget';
        }
        
        return '';
    """)
    return text if text else None


# ═══════════════════════════════════════════════════════
#  PHASE 20: Public API (used by browser_agent.py)
# ═══════════════════════════════════════════════════════

def act_press_key(key):
    """Press a key: enter, tab, escape, up, down, left, right, space, etc."""
    _activate_chrome()
    _physical_key(key)
    return f"Pressed {key}"


def act_run_js(code):
    """Run custom JavaScript. READ-ONLY — for getting page info the other tools can't."""
    return _js(code)
