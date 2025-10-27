import os
from pathlib import Path

print("Current working directory:", os.getcwd())
print()

# Check both data directories
data_dirs = [
    Path("data"),
    Path("backend/data"),
]

for data_dir in data_dirs:
    if data_dir.exists():
        print(f"✓ {data_dir} exists")
        # List contents
        if data_dir.is_dir():
            for item in data_dir.iterdir():
                print(f"  - {item.name}")
    else:
        print(f"✗ {data_dir} does not exist")

# Test path resolution
test_path = Path("data/local/dev/database/local.db")
print(f"\nPath 'data/local/dev/database/local.db' resolves to:")
print(f"  Absolute: {test_path.resolve()}")

test_path = Path("backend/data/local/dev/database/local.db")
print(f"Path 'backend/data/local/dev/database/local.db' resolves to:")
print(f"  Absolute: {test_path.resolve()}")

