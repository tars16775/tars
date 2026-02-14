"""Live test: bracket click fix on Microsoft signup page."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hands.browser import act_goto, act_inspect_page, act_click, act_fill, act_wait

# Step 1: Navigate to signup
print("=" * 60)
print("Step 1: Navigate to signup.live.com")
print(act_goto("https://signup.live.com"))

# Step 2: Look at the page
print("\n" + "=" * 60)
print("Step 2: Inspect page")
page = act_inspect_page()
print(page)

# Step 3: Try clicking [Next] (with brackets - the problematic case)
print("\n" + "=" * 60)
print("Step 3: Click '[Next]' (with brackets)")
result = act_click("[Next]")
print(f"Result: {result}")

# Step 4: Also try clicking "Next" (without brackets)
print("\n" + "=" * 60)
print("Step 4: Click 'Next' (without brackets)")
result2 = act_click("Next")
print(f"Result: {result2}")

print("\n✅ Bracket click test complete")
