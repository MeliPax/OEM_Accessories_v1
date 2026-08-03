"""
Logging configuration for the vehicle model lookup pipeline.

Sets up:
  - Console handler: INFO+ level (user-facing)
  - File handler: DEBUG+ level (detailed troubleshooting)
  - Rotating file handler: Keeps last 5 backup files (10MB each)
  - Structured format: [timestamp] [level] [component] message
"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime


def setup_logging(log_dir="accy_v2/model_lookup/logs", level=logging.DEBUG):
    """
    Configure logging for the entire pipeline.

    Creates:
        - logs/ directory (auto-created if missing)
        - Console output (INFO+) for user visibility
        - File output (DEBUG+) with rotation for detailed diagnostics
        - Structured format with timestamp, level, and component name

    Args:
        log_dir: Directory to store log files (default: accy_v2/model_lookup/logs)
        level: Minimum log level to capture (default: DEBUG)

    Returns:
        Path to the log file created

    Example:
        >>> log_file = setup_logging()
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Process started")
    """

    try:
        # Create logs directory
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # Filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_path / f"refresh_db_ads_{timestamp}.log"

        # Logging format: [TIMESTAMP] [LEVEL] [COMPONENT] message
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)

        # Remove existing handlers (if any) to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Console handler (INFO+) - user-facing
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # File handler (DEBUG+) - detailed diagnostics
        # RotatingFileHandler: keeps last 5 backups, max 10MB per file
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5  # Keep 5 old files
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Log initialization
        root_logger.info(f"Logging initialized | Log file: {log_file}")
        root_logger.debug(f"Console level: INFO | File level: DEBUG")

        return log_file

    except Exception as e:
        print(f"FATAL | Failed to setup logging | Error: {str(e)}")
        raise


def get_logger(component_name):
    """
    Get a logger instance for a specific component.

    Args:
        component_name: Name of the component (e.g., "mapper", "refresh_db_ads", "engine_type")

    Returns:
        logging.Logger instance

    Example:
        >>> logger = get_logger("mapper")
        >>> logger.info("Processing model X")
        [2026-07-28 14:32:15] [INFO    ] [mapper] Processing model X
    """
    return logging.getLogger(component_name)
