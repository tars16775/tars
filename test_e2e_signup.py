"""Full end-to-end: fill Microsoft signup step by step."""
import sys, os, random, string
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hands.browser import act_goto, act_inspect_page, act_click, act_fill, act_wait

# Generate random username
rand = ''.join(random.choices(string.digits, k=6))
username = f"tarsbot{rand}"
email = f"{username}@outlook.com"
password = f"Tars_{rand}_Xq!"

print(f"Test account: {email}")
print(f"Password: {password}")

# Step 1: Navigate
print("\n--- Step 1: Navigate ---")
print(act_goto("https://signup.live.com"))
act_wait(2)

# Step 2: Look
print("\n--- Step 2: Look ---")
page = act_inspect_page()
print(page)

# Step 3: Fill email
print("\n--- Step 3: Fill email ---")
print(act_fill("#floatingLabelInput4", email))

# Step 4: Click Next  
print("\n--- Step 4: Click Next ---")
print(act_click("Next"))
act_wait(3)

# Step 5: Look at new page
print("\n--- Step 5: Look at new page ---")
page2 = act_inspect_page()
print(page2)

# Check if we advanced
if "password" in page2.lower() or "Password" in page2:
    print("\n✅ Advanced to password step!")
elif "error" in page2.lower() or "already" in page2.lower():
    print("\n⚠️ Got an error — username might be taken")
else:
    print("\n❓ Unknown state — check output above")

print("\n--- Test complete ---")
