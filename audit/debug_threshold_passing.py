"""
Debug: Verify that build_dataset correctly passes thresholds to generate_labels.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

# Force fresh import by clearing any cached modules
for mod in list(sys.modules.keys()):
    if 'dataset_builder' in mod or 'labeling' in mod:
        del sys.modules[mod]

from datasets.dataset_builder import build_dataset, compute_train_thresholds
from datasets.labeling import generate_labels, compute_thresholds
from database.db import read_sql
import inspect

# Load data
df = read_sql("SELECT * FROM market_features ORDER BY timestamp")
print(f"Loaded {len(df)} rows, {len(df.columns)} columns")

# 1. Verify the source code of build_dataset
src = inspect.getsource(build_dataset)
lines = src.split('\n')
print("\n=== Checking build_dataset source ===")
for i, line in enumerate(lines):
    if 'thresholds' in line or 'generate_labels' in line or 'def build_dataset' in line:
        print(f"  Line {i}: {line.strip()}")

# 2. Compute thresholds properly
print("\n=== Computing train thresholds ===")
thresholds = compute_train_thresholds(df, label_horizon=10)
print(f"Thresholds keys: {list(thresholds.keys())}")
print(f"fitted_on: {thresholds.get('fitted_on')}")
print(f"UP: {thresholds['up']:.4f}%  DOWN: {thresholds['down']:.4f}%")

# 3. Monkey-patch generate_labels to trace the call
_original_generate = generate_labels
call_count = [0]
thresholds_received = [None]

def _traced_generate(df, horizon_minutes=10, thresholds=None):
    call_count[0] += 1
    thresholds_received[0] = thresholds
    print(f"\nTRACE generate_labels() call #{call_count[0]}:")
    print(f"  horizon_minutes={horizon_minutes}")
    print(f"  thresholds is None: {thresholds is None}")
    if thresholds is not None:
        print(f"  thresholds keys: {list(thresholds.keys())}")
        print(f"  fitted_on: {thresholds.get('fitted_on', 'N/A')}")
    return _original_generate(df, horizon_minutes=horizon_minutes, thresholds=thresholds)

# Use the patched version
import datasets.dataset_builder
datasets.dataset_builder.generate_labels = _traced_generate

# 4. Call build_dataset WITH thresholds
print("\n=== Calling build_dataset with thresholds ===")
ds = build_dataset(df, label_horizon=10, thresholds=thresholds)

print(f"\n=== Results ===")
print(f"generate_labels was called {call_count[0]} time(s)")
print(f"thresholds was None: {thresholds_received[0] is None}")
if thresholds_received[0] is not None:
    print(f"fitted_on match: {thresholds_received[0].get('fitted_on') == 'TRAIN_ONLY'}")
else:
    print("FIX NEEDED: thresholds not reaching generate_labels")
print(f"Dataset rows: {len(ds)}")
