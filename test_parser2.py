"""Test the malformed tool call parser — all known patterns."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brain.llm_client import _parse_failed_tool_call

class FakeError(Exception):
    def __init__(self, msg, body=None):
        super().__init__(msg)
        self.body = body or {}

# Helper to get first tool_use block
def first_tool(response):
    for block in response.content:
        if block.type == "tool_use":
            return block
    return None

# Test 1: XML style with > separator
e1 = FakeError("tool_use_failed", {"failed_generation": '<function=goto>{"url": "https://example.com"}</function>'})
r1 = _parse_failed_tool_call(e1)
assert r1 is not None
t1 = first_tool(r1)
assert t1.name == "goto"
assert t1.input == {"url": "https://example.com"}
print("✅ Test 1: XML with > separator")

# Test 2: XML style without > separator  
e2 = FakeError("tool_use_failed", {"failed_generation": '<function=goto{"url": "https://test.com"}</function>'})
r2 = _parse_failed_tool_call(e2)
assert r2 is not None
assert first_tool(r2).name == "goto"
print("✅ Test 2: XML without > separator")

# Test 3: No args (look)
e3 = FakeError("tool_use_failed", {"failed_generation": '<function=look></function>'})
r3 = _parse_failed_tool_call(e3)
assert r3 is not None
assert first_tool(r3).name == "look"
assert first_tool(r3).input == {}
print("✅ Test 3: No args (look)")

# Test 4: Trailing > on args
e4 = FakeError("tool_use_failed", {"failed_generation": '<function=goto>{"url": "https://signup.live.com"}></function>'})
r4 = _parse_failed_tool_call(e4)
assert r4 is not None
assert first_tool(r4).input.get("url") == "https://signup.live.com"
print("✅ Test 4: Trailing > on args")

# Test 5: Bare tool_name={"args"} (NEW PATTERN)
e5 = FakeError("tool_use_failed", {"failed_generation": 'deploy_browser_agent={"task": "Go to https://signup.live.com and create an account"}'})
r5 = _parse_failed_tool_call(e5)
assert r5 is not None
t5 = first_tool(r5)
assert t5.name == "deploy_browser_agent"
assert "signup.live.com" in t5.input.get("task", "")
print("✅ Test 5: Bare tool_name={args} format")

# Test 6: "attempted to call tool" error pattern (NEW PATTERN)
e6 = FakeError(
    "tool call validation failed: attempted to call tool 'deploy_browser_agent={\"task\": \"Go to https://signup.live.com, fill the first field\"}'",
    {}
)
r6 = _parse_failed_tool_call(e6)
assert r6 is not None
assert first_tool(r6).name == "deploy_browser_agent"
print("✅ Test 6: 'attempted to call tool' error pattern")

# Test 7: Multiple XML calls
e7 = FakeError("tool_use_failed", {"failed_generation": '<function=look></function>\n<function=type>{"selector": "#email", "text": "test@test.com"}</function>'})
r7 = _parse_failed_tool_call(e7)
assert r7 is not None
calls = [b for b in r7.content if b.type == "tool_use"]
assert len(calls) == 2
print("✅ Test 7: Multiple XML calls")

print("\n✅ ALL 7 PARSER TESTS PASSED")
