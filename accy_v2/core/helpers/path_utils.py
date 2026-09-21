"""
Path utilities for converting between absolute and relative paths.

Purpose: Display relative paths in user-facing output (Excel reports, logs) while
maintaining absolute paths internally for file I/O operations.
"""

from pathlib import Path


def get_project_root() -> Path:
    """
    Locate project root by finding run_pipeline.py.

    Searches upward from this module's location until it finds run_pipeline.py,
    which marks the accy_v2/ directory.

    Returns:
        Path: Absolute path to project root (accy_v2 directory)

    Raises:
        RuntimeError: If run_pipeline.py not found after 20 iterations
    """
    current = Path(__file__).parent
    for _ in range(20):
        if (current / "run_pipeline.py").exists():
            return current
        if current == current.parent:
            break
        current = current.parent

    raise RuntimeError(
        f"Could not find project root (run_pipeline.py) starting from {Path(__file__).parent}. "
        "Path utilities require project root to convert paths."
    )


def to_relative_path(absolute_path: str | Path) -> str:
    """
    Convert absolute path to project-relative path for display in output files.

    Used to make Excel reports, logs, and outputs portable and non-machine-specific.

    Args:
        absolute_path: Absolute path (e.g., C:\\Users\\paxm\\...\\accy_v2\\data\\landing_zone\\file.xlsx)

    Returns:
        str: Project-relative path (e.g., accy_v2/data/landing_zone/file.xlsx)
            If path is not under project root, returns the original absolute path as string

    Example:
        >>> to_relative_path("C:\\Users\\paxm\\project\\accy_v2\\data\\landing_zone\\mitsubishi.xlsx")
        'accy_v2/data/landing_zone/mitsubishi.xlsx'
    """
    path = Path(absolute_path).resolve()
    project_root = get_project_root()

    try:
        relative = path.relative_to(project_root)
        return str(relative).replace("\\", "/")  # Use forward slashes for portability
    except ValueError:
        # Path is not under project root, return as-is
        return str(path)


def to_absolute_path(relative_path: str | Path) -> Path:
    """
    Convert project-relative path to absolute path for file I/O operations.

    Used to convert relative paths (from config, logs, or user input) to absolute paths
    needed for actual file operations.

    Args:
        relative_path: Project-relative path (e.g., accy_v2/data/landing_zone/file.xlsx)
                      or absolute path (returned as-is)

    Returns:
        Path: Absolute path object, ready for file I/O

    Example:
        >>> to_absolute_path("accy_v2/data/landing_zone/mitsubishi.xlsx")
        PosixPath('/home/user/project/accy_v2/data/landing_zone/mitsubishi.xlsx')
    """
    if isinstance(relative_path, str):
        relative_path = Path(relative_path)

    # If already absolute, return as-is
    if relative_path.is_absolute():
        return relative_path.resolve()

    # Make relative to project root
    project_root = get_project_root()
    return (project_root / relative_path).resolve()
