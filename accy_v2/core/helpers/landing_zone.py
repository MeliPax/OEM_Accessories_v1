"""Pick the input file for a pipeline run: the file added to the landing zone folder last.

"Added" is the file's creation time in the folder. The modified time can't be used: copying a file into
the folder keeps its original modified time, and opening and saving an older file makes it look newest.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Iterable


def added_time(path: Path) -> float:
    """When the file was added to its folder (its creation time).

    st_birthtime is the creation time on Windows (Python 3.12+) and macOS; on older Windows Pythons,
    st_ctime is the creation time. Where neither exists (Linux), the modified time is the best available.
    """
    st = path.stat()
    birth = getattr(st, "st_birthtime", None)
    if birth is not None:
        return birth
    return st.st_ctime if os.name == "nt" else st.st_mtime


def latest_added(files: Iterable[Path]) -> Path:
    """The file added last; prints which file was picked and which were skipped."""
    files = list(files)
    if not files:
        raise FileNotFoundError("No input files to choose from")
    chosen = max(files, key=added_time)
    print(f"Picked the file added last: {chosen.name} (added {_when(chosen)})")
    for other in sorted(files, key=added_time, reverse=True):
        if other != chosen:
            print(f"  skipped: {other.name} (added {_when(other)})")
    return chosen


INPUT_PATTERNS = ("*.xlsx", "*.csv")


def latest_input_file(folder: Path) -> Path:
    """Standard input pick: the .xlsx or .csv file added to the folder last.

    Skips Excel lock files (~$name.xlsx), which exist while a workbook is open and would
    otherwise look like the newest file.
    """
    folder = Path(folder)
    files = [
        f for pattern in INPUT_PATTERNS for f in folder.glob(pattern)
        if f.is_file() and not f.name.startswith("~$")
    ]
    if not files:
        raise FileNotFoundError(f"No Excel/CSV files found in {folder}")
    return latest_added(files)


def _when(path: Path) -> str:
    return datetime.fromtimestamp(added_time(path)).strftime("%Y-%m-%d %H:%M")
