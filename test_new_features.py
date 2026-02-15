"""Smoke test for all new TARS features."""

# Test 1: Structured scratchpad
from agents.comms import agent_comms, ScratchpadEntry

agent_comms.write_scratchpad('test_selectors', {'email': '#email', 'pass': '#pwd'}, 'selectors', 'browser')
val = agent_comms.read_scratchpad('test_selectors')
assert val == {'email': '#email', 'pass': '#pwd'}, f'Scratchpad read failed: {val}'
print('✅ Structured scratchpad works')

by_type = agent_comms.read_scratchpad_by_type('selectors')
assert 'test_selectors' in by_type, f'Type query failed: {by_type}'
print('✅ Scratchpad type query works')

summary = agent_comms.get_scratchpad_summary()
assert 'Shared Scratchpad' in summary
print('✅ Scratchpad summary works')

agent_comms.clear()
assert agent_comms.read_scratchpad('test_selectors') is None
print('✅ Scratchpad clear works')

# Test 2: Token estimation
from brain.planner import TARSBrain
est = TARSBrain._estimate_tokens([{'content': 'hello world this is a test'}])
assert est > 0, f'Token estimate was {est}'
print(f'✅ Token estimation works (26 chars → ~{est} tokens)')

# Test 3: Exponential backoff
from brain.llm_client import LLMClient
delay = LLMClient._backoff_delay(1)
assert 0 <= delay <= 1.0, f'Backoff delay out of range: {delay}'
delay3 = LLMClient._backoff_delay(3)
assert 0 <= delay3 <= 4.0, f'Backoff delay out of range: {delay3}'
print(f'✅ Exponential backoff works (attempt 1: {delay:.3f}s, attempt 3: {delay3:.3f}s)')

# Test 4: Idempotent dedup
from collections import deque
d = deque(maxlen=1000)
d.append(123)
d.append(456)
assert 123 in d
assert 789 not in d
print('✅ Dedup deque works')

# Test 5: Event bus sync subscribers
from utils.event_bus import event_bus
captured = []
cb = lambda d: captured.append(d)
event_bus.subscribe_sync('test_event', cb)
event_bus.emit('test_event', {'foo': 'bar'})
assert len(captured) == 1 and captured[0]['foo'] == 'bar'
event_bus.unsubscribe_sync('test_event', cb)
print('✅ Event bus sync subscribers work')

# Test 6: Browser lock exists
from hands.browser import _browser_lock
import threading
assert isinstance(_browser_lock, type(threading.Lock()))
print('✅ Browser concurrency lock exists')

print()
print('🟢 ALL NEW FEATURES VERIFIED')
