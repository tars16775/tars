"""
╔══════════════════════════════════════════╗
║      TARS — Voice: iMessage Reader       ║
╚══════════════════════════════════════════╝

Reads incoming iMessages from ~/Library/Messages/chat.db
by polling the SQLite database.
"""

import sqlite3
import time
import os


class IMessageReader:
    def __init__(self, config):
        self.phone = config["imessage"]["owner_phone"]
        self.poll_interval = config["imessage"]["poll_interval"]
        self.db_path = os.path.expanduser("~/Library/Messages/chat.db")
        self._last_message_rowid = self._get_latest_rowid()

    def _get_db_connection(self):
        """Open a read-only connection to chat.db."""
        return sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)

    def _get_latest_rowid(self):
        """Get the ROWID of the most recent message."""
        try:
            conn = self._get_db_connection()
            cursor = conn.execute("SELECT MAX(ROWID) FROM message")
            row = cursor.fetchone()
            conn.close()
            return row[0] if row[0] else 0
        except Exception:
            return 0

    def _get_new_messages(self):
        """Check for new messages from the owner's phone number since last check."""
        try:
            conn = self._get_db_connection()
            cursor = conn.execute("""
                SELECT m.ROWID, m.text, m.is_from_me, m.date
                FROM message m
                LEFT JOIN handle h ON m.handle_id = h.ROWID
                WHERE m.ROWID > ?
                  AND h.id = ?
                  AND m.is_from_me = 0
                  AND m.text IS NOT NULL
                  AND m.text != ''
                ORDER BY m.ROWID ASC
            """, (self._last_message_rowid, self.phone))

            messages = []
            for row in cursor.fetchall():
                rowid, text, is_from_me, date = row
                messages.append({
                    "rowid": rowid,
                    "text": text.strip(),
                    "date": date,
                })
                self._last_message_rowid = max(self._last_message_rowid, rowid)

            conn.close()
            return messages
        except Exception as e:
            print(f"  ⚠️ Error reading chat.db: {e}")
            return []

    def wait_for_reply(self, timeout=300):
        """
        Block and poll chat.db until a new message arrives from the owner.
        Returns the message text, or None if timed out.
        """
        # Update baseline to ignore any messages that arrived before we started waiting
        self._last_message_rowid = self._get_latest_rowid()

        print(f"  📱 Waiting for iMessage reply (timeout: {timeout}s)...")
        start = time.time()

        while time.time() - start < timeout:
            messages = self._get_new_messages()
            if messages:
                # Return the latest message
                reply = messages[-1]["text"]
                print(f"  📱 Received reply: {reply[:80]}...")
                return {"success": True, "content": reply}

            time.sleep(self.poll_interval)

        return {
            "success": False, "error": True,
            "content": f"No reply received within {timeout}s"
        }

    def check_for_kill(self, kill_words):
        """Check if any recent message contains a kill word."""
        messages = self._get_new_messages()
        for msg in messages:
            for kw in kill_words:
                if kw.lower() in msg["text"].lower():
                    return True, msg["text"]
        return False, None
