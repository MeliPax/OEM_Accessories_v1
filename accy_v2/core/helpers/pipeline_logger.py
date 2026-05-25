import logging
from datetime import datetime
from pathlib import Path


class PipelineLogger:
    """
    Records pipeline execution events for developer/ops use.
    Audience: developers and operations.
    Tracks FATAL errors, sheet skips, run events, and record counts.
    Wraps Python's stdlib logging — writes to file and echoes to console.
    """

    def __init__(self, run_id: str, log_path: str):
        self.run_id = run_id
        out = Path(log_path)
        out.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_file = out / f"pipeline_{run_id}_{timestamp}.log"

        self._logger = logging.getLogger(f"OEMAccessories.pipeline.{run_id}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

        self._logger.addHandler(file_handler)
        self._logger.addHandler(console_handler)

    def log_run_start(self, oem: str, file_path: str) -> None:
        self._logger.info(f"RUN START | oem={oem} | file={file_path} | run_id={self.run_id}")

    def log_sheet_start(self, sheet_name: str) -> None:
        self._logger.info(f"SHEET START | sheet={sheet_name}")

    def log_fatal(self, sheet_name: str, step: str, reason: str) -> None:
        self._logger.error(f"FATAL | sheet={sheet_name} | step={step} | reason={reason}")

    def log_sheet_complete(self, sheet_name: str, records_in: int, records_out: int) -> None:
        self._logger.info(
            f"SHEET COMPLETE | sheet={sheet_name} | records_in={records_in} | records_out={records_out}"
        )

    def log_run_complete(self, sheets_processed: int, sheets_skipped: int) -> None:
        self._logger.info(
            f"RUN COMPLETE | sheets_processed={sheets_processed} | sheets_skipped={sheets_skipped}"
        )

    def info(self, msg: str) -> None:
        self._logger.info(msg)

    def warning(self, msg: str) -> None:
        self._logger.warning(msg)

    def debug(self, msg: str) -> None:
        self._logger.debug(msg)
