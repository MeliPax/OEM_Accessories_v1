"""Standard input pick: the .xlsx or .csv file added to the landing zone folder last."""

import sys
import time
from pathlib import Path

import pytest

ACCY_V2 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ACCY_V2.parent), str(ACCY_V2)]

from core.helpers.landing_zone import latest_input_file  # noqa: E402


def _add(folder: Path, name: str) -> Path:
    """Create a file, then pause so the next one has a later creation time."""
    path = folder / name
    path.write_text("x")
    time.sleep(0.05)
    return path


def test_picks_csv_added_after_xlsx(tmp_path):
    _add(tmp_path, "feed.xlsx")
    newest = _add(tmp_path, "feed.csv")
    assert latest_input_file(tmp_path) == newest


def test_picks_xlsx_added_after_csv(tmp_path):
    _add(tmp_path, "feed.csv")
    newest = _add(tmp_path, "feed.xlsx")
    assert latest_input_file(tmp_path) == newest


def test_ignores_excel_lock_files_and_other_types(tmp_path):
    newest = _add(tmp_path, "feed.xlsx")
    _add(tmp_path, "~$feed.xlsx")  # Excel lock file while the workbook is open
    _add(tmp_path, "notes.txt")
    assert latest_input_file(tmp_path) == newest


def test_empty_folder_raises(tmp_path):
    _add(tmp_path, "~$feed.xlsx")
    with pytest.raises(FileNotFoundError, match="No Excel/CSV files"):
        latest_input_file(tmp_path)
