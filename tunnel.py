#!/usr/bin/env python3
"""
TARS Tunnel -- connects the local TARS agent to the cloud relay.

Run this on your Mac alongside tars.py. It forwards all event_bus events
to the Railway-hosted relay server and receives commands back.

Usage:
    python tunnel.py                           # Uses config.yaml relay settings
    python tunnel.py wss://your-app.railway.app/tunnel
"""

import os
import sys
import json
import time
import asyncio
import signal
import threading
import yaml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from utils.event_bus import event_bus


def load_config():
    config_path = os.path.join(BASE_DIR, "config.yaml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


class TARSTunnel:
    def __init__(self, relay_url: str, token: str):
        self.relay_url = relay_url
        self.token = token
        self.ws = None
        self.running = True
        self.reconnect_delay = 1
        self.max_reconnect_delay = 30

    async def connect(self):
        """Connect to the relay and maintain the connection."""
        try:
            import websockets
        except ImportError:
            print("  [!] Install websockets: pip install websockets")
            sys.exit(1)

        while self.running:
            try:
                url = f"{self.relay_url}?token={self.token}"
                print(f"  [>] Connecting to relay: {self.relay_url}")

                async with websockets.connect(url, ping_interval=15, ping_timeout=10) as ws:
                    self.ws = ws
                    self.reconnect_delay = 1
                    print(f"  [+] Tunnel established")

                    # Subscribe to local event_bus and forward events
                    event_queue: asyncio.Queue = asyncio.Queue()

                    def on_event_sync(event_type, data):
                        event = {
                            "type": event_type,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            "ts_unix": time.time(),
                            "data": data or {},
                        }
                        try:
                            event_queue.put_nowait(event)
                        except asyncio.QueueFull:
                            pass

                    # Patch event_bus.emit to also forward events
                    original_emit = event_bus.emit

                    def patched_emit(event_type, data=None):
                        original_emit(event_type, data)
                        on_event_sync(event_type, data)

                    event_bus.emit = patched_emit

                    # Two concurrent tasks: send events and receive commands
                    send_task = asyncio.create_task(self._send_loop(ws, event_queue))
                    recv_task = asyncio.create_task(self._recv_loop(ws))

                    done, pending = await asyncio.wait(
                        [send_task, recv_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for t in pending:
                        t.cancel()

                    # Restore original emit
                    event_bus.emit = original_emit

            except Exception as e:
                print(f"  [!] Tunnel error: {e}")

            if self.running:
                print(f"  [~] Reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

    async def _send_loop(self, ws, queue: asyncio.Queue):
        """Forward local events to the relay."""
        while True:
            event = await queue.get()
            try:
                await ws.send(json.dumps(event))
            except Exception:
                return

    async def _recv_loop(self, ws):
        """Receive commands from the relay (from dashboard) and handle them."""
        async for message in ws:
            if message == "pong":
                continue
            try:
                data = json.loads(message)
                msg_type = data.get("type", "")

                # These are commands from the dashboard relayed through
                # Handle them locally by emitting to the event bus
                # The TARS server.py WebSocket handler will pick them up

                if msg_type == "send_task":
                    event_bus.emit("task_received", {"task": data.get("task", ""), "source": "dashboard"})
                    # Also need to trigger actual task processing
                    # This is handled by the TARSServer._handle_ws_message

                elif msg_type == "kill":
                    event_bus.emit("kill_switch", {"source": "dashboard"})

                elif msg_type in ("get_stats", "get_memory", "save_memory", "update_config"):
                    # Forward to local WebSocket server
                    await self._forward_to_local(message)

            except json.JSONDecodeError:
                pass

    async def _forward_to_local(self, message: str):
        """Forward a command to the local TARS WebSocket server."""
        try:
            import websockets
            async with websockets.connect("ws://localhost:8421") as local_ws:
                await local_ws.send(message)
                response = await asyncio.wait_for(local_ws.recv(), timeout=5)
                # Forward response back through tunnel
                if self.ws:
                    await self.ws.send(response)
        except Exception:
            pass

    def stop(self):
        self.running = False


def main():
    config = load_config()

    # Get relay URL from CLI arg or config
    if len(sys.argv) > 1:
        relay_url = sys.argv[1]
    else:
        relay_url = config.get("relay", {}).get("url", "")
        if not relay_url:
            print("  [!] No relay URL configured.")
            print("  Usage: python tunnel.py wss://your-app.railway.app/tunnel")
            print("  Or add relay.url to config.yaml")
            sys.exit(1)

    token = config.get("relay", {}).get("token", "tars-default-token-change-me")

    print()
    print("  TARS TUNNEL")
    print(f"  Relay: {relay_url}")
    print()

    tunnel = TARSTunnel(relay_url, token)

    def shutdown(*args):
        print("\n  [x] Tunnel shutting down...")
        tunnel.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    asyncio.run(tunnel.connect())


if __name__ == "__main__":
    main()
