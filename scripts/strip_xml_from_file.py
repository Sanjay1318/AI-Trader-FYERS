"""
Remove trailing XML/tool-call markup from a Python file.
Usage: python scripts/strip_xml_from_file.py <filepath>
"""
import sys

if len(sys.argv) < 2:
    print("Usage: python strip_xml_from_file.py <filepath>")
    sys.exit(1)

filepath = sys.argv[1]
with open(filepath, 'rb') as f:
    data = f.read()

# Find the last newline after the last valid Python statement
# Look for patterns like '</parameter>' or '</invoke>' or '</tool_calls>'
import re

# Strip everything after the last newline that's part of the actual code
# Find the last occurrence of proper Python code end markers
text = data.decode('utf-8', errors='replace')

# Find the position of the first XML tag corruption
for tag in ['</parameter>', '</invoke>', '</tool_calls>', '<|DSML']:
    pos = text.find(tag)
    if pos > 0:
        # Go back to find the last newline before this
        nl_pos = text.rfind('\n', 0, pos)
        if nl_pos > 0:
            text = text[:nl_pos]
        break

# Also handle the fullwidth variant
for tag in ['＜/parameter＞', '＜/invoke＞', '＜/tool_calls＞']:
    pos = text.find(tag)
    if pos > 0:
        nl_pos = text.rfind('\n', 0, pos)
        if nl_pos > 0:
            text = text[:nl_pos]
        break

# Clean trailing whitespace
text = text.rstrip() + '\n'

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print(f"Cleaned {filepath}: {len(data)} bytes -> {len(text.encode('utf-8'))} bytes")
