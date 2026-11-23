import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from accy_v2.core.helpers.path_utils import to_relative_path


class DQLogger:
    """
    Accumulates data quality warnings and writes the stakeholder-facing DQ report.
    Audience: business stakeholders / data stewards.
    Only tracks issues found WITHIN the data (DQ_WARNINGs).
    """

    def __init__(self, run_id: str, source_file: str):
        self.run_id = run_id
        self.source_file = to_relative_path(source_file)
        self._records: List[Dict[str, Any]] = []

    def log_warning(
        self,
        sheet_name: str,
        model_name: str,
        record_index: int,
        record_snapshot: Dict,
        rule_violated: str,
        issue_description: str,
    ) -> None:
        self._records.append({
            "run_id": self.run_id,
            "source_file": self.source_file,
            "sheet_name": sheet_name,
            "model_name": model_name,
            "record_index": record_index,
            "record_snapshot": record_snapshot,
            "rule_violated": rule_violated,
            "issue_description": issue_description,
            "logged_at": datetime.utcnow().isoformat(),
        })

    @property
    def warning_count(self) -> int:
        return len(self._records)

    @property
    def records(self) -> List[Dict[str, Any]]:
        return self._records

    def write_dq_report(self, output_path: str, exclude_rules: List[str] = None) -> None:
        """
        Write DQ report to JSON file, optionally filtering out specified rules.

        Args:
            output_path: Directory where report will be written
            exclude_rules: List of rule names to exclude from report (e.g., ["csv_uniqueness_rule"])
                          These rules are still logged to pipeline logs, just not in stakeholder-facing DQ report.
                          Default: ["csv_uniqueness_rule"] to filter noise.
        """
        if exclude_rules is None:
            exclude_rules = ["csv_uniqueness_rule"]

        out = Path(output_path)
        out.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_file = out / f"dq_report_{self.run_id}_{timestamp}.json"

        # Filter records to exclude noise rules
        filtered_records = [
            r for r in self._records
            if r["rule_violated"] not in exclude_rules
        ]

        payload = {
            "run_id": self.run_id,
            "source_file": self.source_file,
            "generated_at": timestamp,
            "total_warnings": len(filtered_records),
            "filtered_rules": exclude_rules if exclude_rules else None,
            "summary": self._build_summary(filtered_records),
            "records": filtered_records,
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

    def _build_summary(self, records: List[Dict[str, Any]] = None) -> Dict:
        """
        Build summary of warnings, optionally using filtered records.

        Args:
            records: Filtered list of records to summarize. If None, uses all records.
        """
        if records is None:
            records = self._records

        by_sheet: Dict[str, Any] = defaultdict(
            lambda: {"total_warnings": 0, "by_rule": defaultdict(int)}
        )
        for rec in records:
            sheet = rec["sheet_name"]
            by_sheet[sheet]["total_warnings"] += 1
            by_sheet[sheet]["by_rule"][rec["rule_violated"]] += 1

        return {
            sheet: {
                "total_warnings": data["total_warnings"],
                "by_rule": dict(data["by_rule"]),
            }
            for sheet, data in by_sheet.items()
        }
