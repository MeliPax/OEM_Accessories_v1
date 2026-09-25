"""Batch DQ Aggregation for Honda Pipeline

Aggregates DQ metrics from multiple files processed in a batch and generates
batch_summary_dq.json with overall quality statistics and per-file details.
"""

import json
from typing import Dict, List, Any, Optional
from collections import defaultdict
from datetime import datetime
from pathlib import Path


class BatchDQAggregator:
    """Aggregates DQ warnings and metrics across all files in a batch."""

    def __init__(self, batch_id: str):
        """Initialize batch aggregator.

        Args:
            batch_id: Unique batch identifier
        """
        self.batch_id = batch_id
        self.file_metrics: List[Dict[str, Any]] = []
        self.all_warnings: List[Dict[str, Any]] = []
        self.start_time = datetime.utcnow()

    def add_file_metrics(
        self,
        file_name: str,
        model_name: str,
        output_metrics: Dict[str, Any],
        dq_warnings: List[Dict[str, Any]],
    ) -> None:
        """Add metrics for a processed file.

        Args:
            file_name: Name of source Excel file
            model_name: Vehicle model name
            output_metrics: Metrics from step5_output.py
            dq_warnings: List of DQ warnings for the file
        """
        file_metric = {
            "file": file_name,
            "model": model_name,
            "timestamp": datetime.utcnow().isoformat(),
            "total_parts": output_metrics.get("total_parts", 0),
            "exact_match": output_metrics.get("exact_match_count", 0),
            "high_confidence": output_metrics.get("high_confidence_count", 0),
            "low_confidence": output_metrics.get("low_confidence_count", 0),
            "not_found": output_metrics.get("not_found_count", 0),
            "dq_warning_count": len(dq_warnings),
            "en_fr_reconciled": output_metrics.get("en_fr_reconciled", 0),
        }

        self.file_metrics.append(file_metric)
        self.all_warnings.extend(dq_warnings)

    def generate_batch_summary(
        self, output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate batch summary statistics.

        Returns:
            Dictionary with aggregated metrics and per-file details
        """
        end_time = datetime.utcnow()
        duration_seconds = (end_time - self.start_time).total_seconds()

        # Aggregate counts
        total_files = len(self.file_metrics)
        total_parts = sum(f["total_parts"] for f in self.file_metrics)
        total_exact = sum(f["exact_match"] for f in self.file_metrics)
        total_high_conf = sum(f["high_confidence"] for f in self.file_metrics)
        total_low_conf = sum(f["low_confidence"] for f in self.file_metrics)
        total_not_found = sum(f["not_found"] for f in self.file_metrics)
        total_dq_warnings = len(self.all_warnings)

        # Calculate quality metrics
        match_rate = (
            (total_exact + total_high_conf) / total_parts
            if total_parts > 0
            else 0
        )
        not_found_rate = total_not_found / total_parts if total_parts > 0 else 0

        # Group warnings by rule type
        warnings_by_rule = defaultdict(int)
        for warning in self.all_warnings:
            rule_type = warning.get("rule_type", "unknown")
            warnings_by_rule[rule_type] += 1

        # Group warnings by severity
        warnings_by_severity = defaultdict(int)
        for warning in self.all_warnings:
            severity = warning.get("severity", "WARNING")
            warnings_by_severity[severity] += 1

        # Identify files with issues
        files_with_issues = [
            f for f in self.file_metrics if f["dq_warning_count"] > 0
        ]

        # Create summary
        summary = {
            "batch_id": self.batch_id,
            "generated_at": end_time.isoformat(),
            "duration_seconds": duration_seconds,
            "files": {
                "total": total_files,
                "with_issues": len(files_with_issues),
                "processed": total_files,
            },
            "parts": {
                "total": total_parts,
                "exact_match": {
                    "count": total_exact,
                    "percentage": (total_exact / total_parts * 100) if total_parts > 0 else 0,
                },
                "high_confidence": {
                    "count": total_high_conf,
                    "percentage": (total_high_conf / total_parts * 100) if total_parts > 0 else 0,
                },
                "low_confidence": {
                    "count": total_low_conf,
                    "percentage": (total_low_conf / total_parts * 100) if total_parts > 0 else 0,
                },
                "not_found": {
                    "count": total_not_found,
                    "percentage": (total_not_found / total_parts * 100) if total_parts > 0 else 0,
                },
                "overall_match_rate": match_rate,
                "overall_not_found_rate": not_found_rate,
            },
            "quality": {
                "total_dq_warnings": total_dq_warnings,
                "warnings_by_rule": dict(warnings_by_rule),
                "warnings_by_severity": dict(warnings_by_severity),
                "average_warnings_per_file": (
                    total_dq_warnings / total_files if total_files > 0 else 0
                ),
            },
            "reconciliation": {
                "total_en_fr_reconciled": sum(f["en_fr_reconciled"] for f in self.file_metrics),
            },
        }

        # Add per-file details
        summary["file_details"] = self.file_metrics

        # Add files with issues
        if files_with_issues:
            summary["files_with_issues"] = [
                {
                    "file": f["file"],
                    "model": f["model"],
                    "warning_count": f["dq_warning_count"],
                    "recommended_action": self._get_recommended_action(f),
                }
                for f in files_with_issues
            ]

        # Write to JSON if output_dir provided
        if output_dir:
            self._write_batch_summary(summary, output_dir)

        return summary

    def _get_recommended_action(self, file_metric: Dict[str, Any]) -> str:
        """Determine recommended action for a file based on metrics.

        Args:
            file_metric: File-level metrics dictionary

        Returns:
            Recommended action string
        """
        not_found_pct = (
            file_metric["not_found"] / file_metric["total_parts"] * 100
            if file_metric["total_parts"] > 0
            else 0
        )
        low_conf_pct = (
            file_metric["low_confidence"] / file_metric["total_parts"] * 100
            if file_metric["total_parts"] > 0
            else 0
        )

        if not_found_pct > 20:
            return f"HIGH: {not_found_pct:.1f}% parts not found in model database - verify source data"
        elif not_found_pct > 10:
            return f"MEDIUM: {not_found_pct:.1f}% parts not found - review trim specifications"
        elif low_conf_pct > 30:
            return f"MEDIUM: {low_conf_pct:.1f}% low-confidence matches - manual review recommended"
        elif file_metric["dq_warning_count"] > 10:
            return "REVIEW: Multiple DQ issues detected - investigate and reconcile"
        else:
            return "OK: Proceed with confidence"

    def _write_batch_summary(self, summary: Dict[str, Any], output_dir: str) -> str:
        """Write batch summary to JSON file.

        Args:
            summary: Summary dictionary
            output_dir: Output directory path

        Returns:
            Path to written file
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        filename = f"batch_summary_dq_{self.batch_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        file_path = output_path / filename

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)

        return str(file_path)

    def get_batch_issues_report(self) -> str:
        """Generate human-readable batch issues report.

        Returns:
            Formatted report string
        """
        lines = [
            "=" * 80,
            f"BATCH DQ SUMMARY: {self.batch_id}",
            "=" * 80,
            f"Generated: {datetime.utcnow().isoformat()}",
            "",
        ]

        # Files summary
        total_files = len(self.file_metrics)
        files_with_issues = sum(1 for f in self.file_metrics if f["dq_warning_count"] > 0)
        lines.extend([
            f"Files Processed: {total_files}",
            f"Files with Issues: {files_with_issues}",
            f"Total Parts: {sum(f['total_parts'] for f in self.file_metrics)}",
            f"Total DQ Warnings: {len(self.all_warnings)}",
            "",
        ])

        # Quality breakdown
        total_parts = sum(f["total_parts"] for f in self.file_metrics)
        if total_parts > 0:
            lines.extend([
                "Quality Breakdown:",
                f"  Exact Match: {sum(f['exact_match'] for f in self.file_metrics)} ({sum(f['exact_match'] for f in self.file_metrics)/total_parts*100:.1f}%)",
                f"  High Confidence: {sum(f['high_confidence'] for f in self.file_metrics)} ({sum(f['high_confidence'] for f in self.file_metrics)/total_parts*100:.1f}%)",
                f"  Low Confidence: {sum(f['low_confidence'] for f in self.file_metrics)} ({sum(f['low_confidence'] for f in self.file_metrics)/total_parts*100:.1f}%)",
                f"  Not Found: {sum(f['not_found'] for f in self.file_metrics)} ({sum(f['not_found'] for f in self.file_metrics)/total_parts*100:.1f}%)",
                "",
            ])

        # Top warning rules
        from collections import Counter
        rule_counts = Counter(w.get("rule_type") for w in self.all_warnings)
        if rule_counts:
            lines.append("Top DQ Rules:")
            for rule, count in rule_counts.most_common(5):
                lines.append(f"  {rule}: {count} warnings")
            lines.append("")

        # Files with issues
        if files_with_issues > 0:
            lines.append("Files with Issues:")
            for f in self.file_metrics:
                if f["dq_warning_count"] > 0:
                    lines.append(f"  {f['file']}: {f['dq_warning_count']} warnings")

        lines.append("=" * 80)
        return "\n".join(lines)
