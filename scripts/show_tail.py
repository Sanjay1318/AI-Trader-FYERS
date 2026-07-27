from pathlib import Path

path = Path("backend/app.py")

lines = path.read_text(encoding="utf-8").splitlines()

print("=" * 80)
print(f"Total lines: {len(lines)}")
print("=" * 80)

start = max(0, len(lines) - 40)

for i in range(start, len(lines)):
    print(f"{i+1}: {lines[i]}")

