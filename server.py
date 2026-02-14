"""
╔══════════════════════════════════════════╗
║       TARS — Dashboard Server            ║
╚══════════════════════════════════════════╝

WebSocket server for real-time events +
HTTP server to serve the dashboard UI.
Runs on localhost:8420
"""

import asyncio
import json
import os
import threading
import mimetypes
from http.server import HTTPServer, SimpleHTTPRequestHandler
import websockets

from utils.event_bus import event_bus

# Prefer built Vite output (dashboard/dist/), fall back to dashboard/ root
_base = os.path.dirname(os.path.abspath(__file__))
_dist = os.path.join(_base, "dashboard", "dist")
DASHBOARD_DIR = _dist if os.path.isdir(_dist) else os.path.join(_base, "dashboard")
WS_PORT = 8421
HTTP_PORT = 8420


class DashboardHTTPHandler(SimpleHTTPRequestHandler):
    """Serve dashboard static files."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def log_message(self, format, *args):
        pass  # Suppress HTTP logs

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()


class TARSServer:
    """Runs the dashboard HTTP server + WebSocket server."""

    def __init__(self, memory_manager=None, tars_instance=None):
        self.memory = memory_manager
        self.tars = tars_instance
        self._ws_loop = None
        self._thread = None

    def start(self):
        """Start both servers in a background thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        """Run the async event loop for WebSocket + HTTP."""
        self._ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._ws_loop)
        event_bus.set_loop(self._ws_loop)

        # Start HTTP server in a sub-thread
        http_thread = threading.Thread(target=self._run_http, daemon=True)
        http_thread.start()

        # Start WebSocket server
        self._ws_loop.run_until_complete(self._run_ws())

    def _run_http(self):
        """Run HTTP server for dashboard static files."""
        server = HTTPServer(("0.0.0.0", HTTP_PORT), DashboardHTTPHandler)
        server.serve_forever()

    async def _run_ws(self):
        """Run WebSocket server for real-time events."""
        async def handler(websocket, path=None):
            # Send history to new client
            for event in event_bus.get_history():
                try:
                    await websocket.send(json.dumps(event))
                except Exception:
                    return

            # Subscribe for new events
            event_bus.subscribe(websocket.send)
            try:
                async for message in websocket:
                    await self._handle_ws_message(message, websocket)
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                event_bus.unsubscribe(websocket.send)

        async with websockets.serve(handler, "0.0.0.0", WS_PORT):
            await asyncio.Future()  # Run forever

    async def _handle_ws_message(self, message, websocket):
        """Handle incoming WebSocket messages from the dashboard."""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "get_stats":
                stats = event_bus.get_stats()
                await websocket.send(json.dumps({"type": "stats", "data": stats}))

            elif msg_type == "get_memory":
                if self.memory:
                    mem_data = {
                        "context": self.memory._read(self.memory.context_file),
                        "preferences": self.memory._read(self.memory.preferences_file),
                        "active_project": self.memory.get_active_project(),
                    }
                    await websocket.send(json.dumps({"type": "memory_data", "data": mem_data}))

            elif msg_type == "save_memory":
                if self.memory:
                    field = data.get("field", "")
                    content = data.get("content", "")
                    if field == "context":
                        self.memory.update_context(content)
                    elif field == "preferences":
                        self.memory.update_preferences(content)
                    await websocket.send(json.dumps({"type": "memory_saved", "data": {"field": field}}))

            elif msg_type == "send_task":
                task = data.get("task", "")
                if task and self.tars:
                    event_bus.emit("task_received", {"task": task, "source": "dashboard"})
                    # Process in a thread so we don't block
                    threading.Thread(target=self.tars._process_task, args=(task,), daemon=True).start()

            elif msg_type == "kill":
                event_bus.emit("kill_switch", {"source": "dashboard"})
                if self.tars:
                    self.tars.running = False

            elif msg_type == "update_config":
                key = data.get("key", "")
                value = data.get("value")
                if self.tars and key:
                    keys = key.split(".")
                    cfg = self.tars.config
                    for k in keys[:-1]:
                        cfg = cfg[k]
                    cfg[keys[-1]] = value
                    event_bus.emit("config_updated", {"key": key, "value": value})

        except Exception as e:
            await websocket.send(json.dumps({"type": "error", "data": {"message": str(e)}}))
