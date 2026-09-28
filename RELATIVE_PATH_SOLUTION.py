"""
Smart relative path solution for loading Honda data

This works from any notebook location by finding the project root
"""

from pathlib import Path

def get_project_root():
    """Find the OEM_Accessories_v1 project root"""
    current = Path.cwd()

    # Search up the directory tree for the project root
    while current != current.parent:
        # Check if we're in the project by looking for accy_v2
        if (current / "accy_v2").exists():
            return current
        current = current.parent

    # Fallback: assume current directory is root
    return Path.cwd()

# Get project root
project_root = get_project_root()

# Build path to data file
landing_zone = project_root / "accy_v2/data/landing_zone/honda/may_2026"
civic_5d_file = landing_zone / "CVIC5D.xlsx"

print(f"Project root: {project_root}")
print(f"Landing zone: {landing_zone}")
print(f"File: {civic_5d_file}\n")

if not civic_5d_file.exists():
    print(f"[ERROR] File not found: {civic_5d_file}")
else:
    print(f"[OK] File found: {civic_5d_file.name}")
    print(f"  Size: {civic_5d_file.stat().st_size / (1024**2):.2f} MB")
