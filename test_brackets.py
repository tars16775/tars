"""Quick test for the [Next] bracket fix."""

# Test CSS detection heuristic
def is_css(target):
    return len(target) > 0 and (
        target[0] in ("#", ".") or 
        (target[0] == "[" and "=" in target)
    )

# These should NOT be CSS
assert not is_css("[Next]"), "[Next] should NOT be CSS"
assert not is_css("[Help and feedback]"), "[Help and feedback] should NOT be CSS"
assert not is_css("[Sign in]"), "[Sign in] should NOT be CSS"

# These SHOULD be CSS
assert is_css("#floatingLabelInput4"), "#id should be CSS"
assert is_css(".btn-primary"), ".class should be CSS"
assert is_css('[name="email"]'), '[name="email"] should be CSS'
assert is_css('[aria-label="Username"]'), '[aria-label=...] should be CSS'

print("✅ CSS detection heuristic: all tests pass")

# Test bracket stripping in act_click
def clean_target(target):
    clean = target.strip()
    if clean.startswith("[") and clean.endswith("]") and "=" not in clean:
        clean = clean[1:-1]
    return clean

assert clean_target("[Next]") == "Next"
assert clean_target("[Help and feedback]") == "Help and feedback"
assert clean_target("[Sign in]") == "Sign in"
assert clean_target("Next") == "Next"  # no change for plain text
assert clean_target('#submit') == "#submit"  # no change for CSS
assert clean_target('[name="email"]') == '[name="email"]'  # CSS preserved

print("✅ Bracket stripping: all tests pass")
print("✅ ALL TESTS PASSED")
