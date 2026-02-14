"""Debug parser test 5."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brain.llm_client import _parse_failed_tool_call

class FakeError(Exception):
    def __init__(self, msg, body=None):
        super().__init__(msg)
        self.body = body or {}

e5 = FakeError("tool_use_failed", {"failed_generation": 'deploy_browser_agent={"task": "Go to https://signup.live.com and create an account"}'})
r5 = _parse_failed_tool_call(e5)
if r5:
    for i, block in enumerate(r5.content):
        print(f"Block {i}: type={block.type}, name={getattr(block, 'name', 'N/A')}, input={getattr(block, 'input', 'N/A')}")
else:
    print("Parser returned None")
