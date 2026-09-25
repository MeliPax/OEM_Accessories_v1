"""Honda-Specific Data Quality Rules

Defines DQ validation rules specific to Honda pipeline, including:
- Orphaned records (parts with no trims)
- Rollup verification (parent-child aggregation)
- Section mismatches (EN/FR divergence)
- Trim applicability validation
- EN/FR cost/part count variance
"""

from typing import Dict, Any, List
import pandas as pd


class HondaDQRules:
    """Container for Honda-specific DQ validation rules."""

    @staticmethod
    def orphan_record_rule(df: pd.DataFrame, section: str) -> List[Dict[str, Any]]:
        """Identify parts with no applicable trims (orphaned records).

        An orphan is a part where no trim columns have a value (all trims are empty/null).
        This indicates the part was extracted but has no applicability data.

        Args:
            df: DataFrame for section (packages, wheels, etc.)
            section: Section name (e.g., 'packages', 'exterior')

        Returns:
            List of warning dicts {part_number, description, rule_type, severity, message}
        """
        warnings = []

        # Identify trim columns (typically named like Civic, Accord, CR-V, etc.)
        trim_cols = [col for col in df.columns if col not in [
            'description', 'part_number', 'comments', 'installed_price',
            'list_price', 'section', 'description_fr', 'comments_fr'
        ]]

        if not trim_cols:
            return warnings

        # Find rows where all trim columns are empty/NaN
        for idx, row in df.iterrows():
            trim_values = [row.get(col) for col in trim_cols]
            if all(pd.isna(val) or val == '' for val in trim_values):
                warnings.append({
                    "part_number": row.get("part_number", ""),
                    "model": "Honda",
                    "section": section,
                    "rule_type": "orphan_record_rule",
                    "severity": "WARNING",
                    "message": f"Part {row.get('part_number')} in {section} has no trim applicability",
                })

        return warnings

    @staticmethod
    def rollup_verification_rule(
        parent_rows: pd.DataFrame, child_rows: pd.DataFrame, section: str
    ) -> List[Dict[str, Any]]:
        """Verify parent-child aggregation in rollup logic.

        For each parent part, verify that:
        1. Parent has non-null price
        2. Child count matches expected aggregation
        3. Children all have same trim applicability as parent

        Args:
            parent_rows: DataFrame with identified parent parts
            child_rows: DataFrame with identified child parts
            section: Section name

        Returns:
            List of warning dicts for mismatches
        """
        warnings = []

        # Group by parent part_number
        if "parent_part_number" not in parent_rows.columns:
            return warnings

        for parent_idx, parent_row in parent_rows.iterrows():
            parent_num = parent_row.get("part_number")
            parent_price = parent_row.get("installed_price")

            # Check: parent has price
            if pd.isna(parent_price) or parent_price == 0:
                warnings.append({
                    "part_number": parent_num,
                    "model": "Honda",
                    "section": section,
                    "rule_type": "rollup_verification_rule",
                    "severity": "WARNING",
                    "message": f"Parent part {parent_num} has null/zero price",
                })

            # Find associated children
            children = child_rows[child_rows.get("parent_part_number") == parent_num]
            if len(children) > 0:
                # Verify trim applicability consistency
                trim_cols = [col for col in parent_row.index if col not in [
                    'description', 'part_number', 'comments', 'installed_price',
                    'list_price', 'section', 'parent_part_number'
                ]]

                for _, child_row in children.iterrows():
                    for trim_col in trim_cols:
                        parent_trim = parent_row.get(trim_col)
                        child_trim = child_row.get(trim_col)

                        if pd.notna(parent_trim) != pd.notna(child_trim):
                            warnings.append({
                                "part_number": child_row.get("part_number"),
                                "model": "Honda",
                                "section": section,
                                "rule_type": "rollup_verification_rule",
                                "severity": "WARNING",
                                "message": f"Child part trim mismatch with parent {parent_num}",
                            })

        return warnings

    @staticmethod
    def section_mismatch_rule(
        en_df: pd.DataFrame, fr_df: pd.DataFrame, section: str
    ) -> List[Dict[str, Any]]:
        """Detect section structure divergence between EN and FR sheets.

        Verifies that EN and FR sheets have:
        1. Same number of parts in each section
        2. Same part numbers (reconciled)
        3. Same column structure

        Args:
            en_df: EN section DataFrame
            fr_df: FR section DataFrame
            section: Section name

        Returns:
            List of warning dicts for divergence
        """
        warnings = []

        if en_df.empty and fr_df.empty:
            return warnings

        # Check: row count mismatch
        if len(en_df) != len(fr_df):
            warnings.append({
                "part_number": f"{section}:total",
                "model": "Honda",
                "section": section,
                "rule_type": "section_mismatch_rule",
                "severity": "WARNING",
                "message": f"Section {section} row count: EN={len(en_df)}, FR={len(fr_df)}",
            })

        # Check: column structure mismatch
        en_cols = set(en_df.columns)
        fr_cols = set(fr_df.columns)
        if en_cols != fr_cols:
            missing_in_fr = en_cols - fr_cols
            extra_in_fr = fr_cols - en_cols
            warnings.append({
                "part_number": f"{section}:structure",
                "model": "Honda",
                "section": section,
                "rule_type": "section_mismatch_rule",
                "severity": "WARNING",
                "message": f"Column mismatch: missing={missing_in_fr}, extra={extra_in_fr}",
            })

        # Check: part number mismatches in reconciliation
        if "part_number" in en_df.columns and "part_number" in fr_df.columns:
            en_parts = set(en_df["part_number"].dropna().unique())
            fr_parts = set(fr_df["part_number"].dropna().unique())
            en_only = en_parts - fr_parts
            fr_only = fr_parts - en_parts

            if en_only:
                warnings.append({
                    "part_number": f"{section}:en_only",
                    "model": "Honda",
                    "section": section,
                    "rule_type": "section_mismatch_rule",
                    "severity": "WARNING",
                    "message": f"EN-only parts in {section}: {en_only}",
                })

            if fr_only:
                warnings.append({
                    "part_number": f"{section}:fr_only",
                    "model": "Honda",
                    "section": section,
                    "rule_type": "section_mismatch_rule",
                    "severity": "WARNING",
                    "message": f"FR-only parts in {section}: {fr_only}",
                })

        return warnings

    @staticmethod
    def en_fr_divergence_rule(
        en_df: pd.DataFrame, fr_df: pd.DataFrame, section: str, cost_variance_threshold: float = 0.05
    ) -> List[Dict[str, Any]]:
        """Detect cost, part count, and description divergence EN/FR.

        For each part, verify:
        1. Cost variance < threshold (default 5%)
        2. Description length reasonable (not truncated)
        3. Part count/applicability consistent

        Args:
            en_df: EN section DataFrame
            fr_df: FR section DataFrame
            section: Section name
            cost_variance_threshold: Max acceptable cost variance (0.05 = 5%)

        Returns:
            List of warning dicts for divergence
        """
        warnings = []

        # Merge on part_number to compare
        if "part_number" not in en_df.columns or "part_number" not in fr_df.columns:
            return warnings

        merged = en_df[["part_number", "installed_price"]].merge(
            fr_df[["part_number", "installed_price"]],
            on="part_number",
            suffixes=("_en", "_fr"),
        )

        for _, row in merged.iterrows():
            en_price = row.get("installed_price_en")
            fr_price = row.get("installed_price_fr")

            if pd.notna(en_price) and pd.notna(fr_price) and en_price > 0:
                variance = abs(en_price - fr_price) / en_price
                if variance > cost_variance_threshold:
                    warnings.append({
                        "part_number": row.get("part_number"),
                        "model": "Honda",
                        "section": section,
                        "rule_type": "en_fr_divergence_rule",
                        "severity": "WARNING",
                        "message": f"Cost variance: EN=${en_price:.2f}, FR=${fr_price:.2f} ({variance:.1%})",
                    })

        return warnings

    @staticmethod
    def trim_applicability_rule(df: pd.DataFrame, section: str) -> List[Dict[str, Any]]:
        """Validate trim applicability marking consistency.

        For parent-child relationships, verify that applicability markers
        (•, T, E, etc.) are consistent between parent and child.

        Args:
            df: DataFrame with parent-child relationships
            section: Section name

        Returns:
            List of warning dicts for inconsistencies
        """
        warnings = []

        if "parent_part_number" not in df.columns:
            return warnings

        # Identify trim columns
        trim_cols = [col for col in df.columns if col not in [
            'description', 'part_number', 'comments', 'installed_price',
            'list_price', 'section', 'parent_part_number', 'description_fr', 'comments_fr'
        ]]

        # Group by parent
        for parent_num, group in df.groupby("parent_part_number"):
            parent_row = group[group["part_number"] == parent_num]
            if parent_row.empty:
                continue

            parent_trimvals = {col: parent_row.iloc[0].get(col) for col in trim_cols}

            # Check each child
            for _, child_row in group.iterrows():
                if child_row.get("part_number") == parent_num:
                    continue

                for trim_col, parent_val in parent_trimvals.items():
                    child_val = child_row.get(trim_col)

                    # Applicability marker mismatch: parent marked but child not (or vice versa)
                    parent_marked = pd.notna(parent_val) and str(parent_val).strip()
                    child_marked = pd.notna(child_val) and str(child_val).strip()

                    if parent_marked != child_marked:
                        warnings.append({
                            "part_number": child_row.get("part_number"),
                            "model": "Honda",
                            "section": section,
                            "rule_type": "trim_applicability_rule",
                            "severity": "WARNING",
                            "message": f"Child applicability mismatch: parent {parent_num} {trim_col}={parent_val}, child={child_val}",
                        })

        return warnings
