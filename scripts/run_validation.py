from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Iterable
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict


@dataclass
class CheckResult:
    check_name: str
    table: str
    severity: str  # "CRITICAL" | "WARN"
    passed: bool
    failed_count: int
    sample_failures: list[dict[str, Any]]


def results_to_json(results: list[CheckResult]) -> list[dict[str, Any]]:
    return [asdict(r) for r in results]


def results_to_dataframe(results: list[CheckResult]) -> pd.DataFrame:
    return pd.DataFrame([asdict(r) for r in results])


def load_csvs(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    data_dir = Path(data_dir)
    dfs = {}
    for name in ["suppliers", "parts", "purchase_orders", "po_lines"]:
        path = data_dir / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing file: {path}")
        dfs[name] = pd.read_csv(path)
    return dfs


def _sample_rows(df: pd.DataFrame, mask: pd.Series, cols: list[str], n: int = 5) -> list[dict[str, Any]]:
    if mask is None or mask.sum() == 0:
        return []
    sample = df.loc[mask, cols].head(n)
    return sample.to_dict(orient="records")


def check_required_columns(df: pd.DataFrame, table: str, required: Iterable[str], severity: str = "CRITICAL") -> CheckResult:
    required = list(required)
    missing = [c for c in required if c not in df.columns]
    passed = len(missing) == 0
    return CheckResult(
        check_name="required_columns",
        table=table,
        severity=severity,
        passed=passed,
        failed_count=len(missing),
        sample_failures=[{"missing_column": c} for c in missing][:5],
    )


def check_primary_key_unique(df: pd.DataFrame, table: str, pk: str, severity: str = "CRITICAL") -> CheckResult:
    if pk not in df.columns:
        return CheckResult("primary_key_unique", table, severity, False, 1, [{"error": f"pk column missing: {pk}"}])
    dup_mask = df[pk].duplicated(keep=False) & df[pk].notna()
    failed_count = int(dup_mask.sum())
    return CheckResult(
        check_name="primary_key_unique",
        table=table,
        severity=severity,
        passed=failed_count == 0,
        failed_count=failed_count,
        sample_failures=_sample_rows(df, dup_mask, [pk]),
    )


def check_not_null(df: pd.DataFrame, table: str, col: str, severity: str = "CRITICAL") -> CheckResult:
    if col not in df.columns:
        return CheckResult("not_null", table, severity, False, 1, [{"error": f"column missing: {col}"}])
    null_mask = df[col].isna()
    failed_count = int(null_mask.sum())
    return CheckResult(
        check_name=f"not_null:{col}",
        table=table,
        severity=severity,
        passed=failed_count == 0,
        failed_count=failed_count,
        sample_failures=_sample_rows(df, null_mask, [col]),
    )


def check_allowed_values(df: pd.DataFrame, table: str, col: str, allowed: set[Any], severity: str = "CRITICAL") -> CheckResult:
    if col not in df.columns:
        return CheckResult("allowed_values", table, severity, False, 1, [{"error": f"column missing: {col}"}])
    bad_mask = df[col].notna() & ~df[col].isin(list(allowed))
    failed_count = int(bad_mask.sum())
    return CheckResult(
        check_name=f"allowed_values:{col}",
        table=table,
        severity=severity,
        passed=failed_count == 0,
        failed_count=failed_count,
        sample_failures=_sample_rows(df, bad_mask, [col]),
    )


def check_numeric_min(df: pd.DataFrame, table: str, col: str, min_value: float, severity: str = "CRITICAL") -> CheckResult:
    if col not in df.columns:
        return CheckResult("numeric_min", table, severity, False, 1, [{"error": f"column missing: {col}"}])
    series = pd.to_numeric(df[col], errors="coerce")
    bad_mask = series.notna() & (series < min_value)
    failed_count = int(bad_mask.sum())
    return CheckResult(
        check_name=f"numeric_min:{col}",
        table=table,
        severity=severity,
        passed=failed_count == 0,
        failed_count=failed_count,
        sample_failures=_sample_rows(df.assign(**{col: series}), bad_mask, [col]),
    )


def check_fk_exists(child: pd.DataFrame, parent: pd.DataFrame, table: str, fk_col: str, parent_key: str, severity: str = "CRITICAL") -> CheckResult:
    if fk_col not in child.columns:
        return CheckResult("fk_exists", table, severity, False, 1, [{"error": f"fk column missing: {fk_col}"}])
    if parent_key not in parent.columns:
        return CheckResult("fk_exists", table, severity, False, 1, [{"error": f"parent key missing: {parent_key}"}])

    parent_keys = set(parent[parent_key].dropna().unique().tolist())
    bad_mask = child[fk_col].notna() & ~child[fk_col].isin(list(parent_keys))
    failed_count = int(bad_mask.sum())
    return CheckResult(
        check_name=f"fk_exists:{fk_col}->{parent_key}",
        table=table,
        severity=severity,
        passed=failed_count == 0,
        failed_count=failed_count,
        sample_failures=_sample_rows(child, bad_mask, [fk_col]),
    )


def check_line_amount_math(po_lines: pd.DataFrame, severity: str = "CRITICAL", tolerance: float = 0.01) -> CheckResult:
    table = "po_lines"
    needed = ["qty", "unit_price", "line_amount"]
    for c in needed:
        if c not in po_lines.columns:
            return CheckResult("line_amount_math", table, severity, False, 1, [{"error": f"missing column: {c}"}])

    qty = pd.to_numeric(po_lines["qty"], errors="coerce")
    unit_price = pd.to_numeric(po_lines["unit_price"], errors="coerce")
    line_amount = pd.to_numeric(po_lines["line_amount"], errors="coerce")

    expected = qty * unit_price
    diff = (line_amount - expected).abs()

    bad_mask = diff.notna() & (diff > tolerance)
    failed_count = int(bad_mask.sum())

    tmp = po_lines.copy()
    tmp["_expected"] = expected
    tmp["_diff"] = diff

    return CheckResult(
        check_name="line_amount_math",
        table=table,
        severity=severity,
        passed=failed_count == 0,
        failed_count=failed_count,
        sample_failures=_sample_rows(tmp, bad_mask, ["qty", "unit_price", "line_amount", "_expected", "_diff"]),
    )


def check_po_totals_reconcile(purchase_orders: pd.DataFrame, po_lines: pd.DataFrame, severity: str = "WARN", tolerance: float = 0.05) -> CheckResult:
    table = "purchase_orders"
    needed_po = ["po_id", "total_amount"]
    needed_lines = ["po_id", "line_amount"]
    for c in needed_po:
        if c not in purchase_orders.columns:
            return CheckResult("po_totals_reconcile", table, severity, False, 1, [{"error": f"missing purchase_orders.{c}"}])
    for c in needed_lines:
        if c not in po_lines.columns:
            return CheckResult("po_totals_reconcile", table, severity, False, 1, [{"error": f"missing po_lines.{c}"}])

    lines_amount = pd.to_numeric(po_lines["line_amount"], errors="coerce")
    po_lines2 = po_lines.copy()
    po_lines2["line_amount"] = lines_amount

    sums = po_lines2.groupby("po_id", dropna=False)["line_amount"].sum().reset_index()
    merged = purchase_orders[["po_id", "total_amount"]].merge(sums, on="po_id", how="left", suffixes=("_po", "_lines"))

    merged["total_amount"] = pd.to_numeric(merged["total_amount"], errors="coerce")
    merged["line_amount"] = merged["line_amount"].fillna(0)

    merged["_diff"] = (merged["total_amount"] - merged["line_amount"]).abs()
    bad_mask = merged["_diff"].notna() & (merged["_diff"] > tolerance)

    failed_count = int(bad_mask.sum())
    return CheckResult(
        check_name="po_totals_reconcile",
        table=table,
        severity=severity,
        passed=failed_count == 0,
        failed_count=failed_count,
        sample_failures=merged.loc[bad_mask, ["po_id", "total_amount", "line_amount", "_diff"]].head(5).to_dict(orient="records"),
    )


def run_all_checks(data_dir: str | Path) -> list[CheckResult]:
    dfs = load_csvs(data_dir)
    suppliers = dfs["suppliers"]
    parts = dfs["parts"]
    purchase_orders = dfs["purchase_orders"]
    po_lines = dfs["po_lines"]

    results = []

    # Schema
    results.append(check_required_columns(suppliers, "suppliers", ["supplier_id", "supplier_name", "status", "country"]))
    results.append(check_required_columns(parts, "parts", ["part_id", "part_name", "part_type", "uom", "is_active"]))
    results.append(check_required_columns(purchase_orders, "purchase_orders", ["po_id", "supplier_id", "po_date", "currency", "total_amount", "status"]))
    results.append(check_required_columns(po_lines, "po_lines", ["po_line_id", "po_id", "part_id", "qty", "unit_price", "line_amount"]))

    # PK
    results.append(check_primary_key_unique(suppliers, "suppliers", "supplier_id"))
    results.append(check_primary_key_unique(parts, "parts", "part_id"))
    results.append(check_primary_key_unique(purchase_orders, "purchase_orders", "po_id"))
    results.append(check_primary_key_unique(po_lines, "po_lines", "po_line_id"))

    # Not null IDs
    results.append(check_not_null(suppliers, "suppliers", "supplier_id"))
    results.append(check_not_null(parts, "parts", "part_id"))
    results.append(check_not_null(purchase_orders, "purchase_orders", "po_id"))
    results.append(check_not_null(po_lines, "po_lines", "po_line_id"))
    results.append(check_not_null(purchase_orders, "purchase_orders", "supplier_id"))
    results.append(check_not_null(po_lines, "po_lines", "po_id"))
    results.append(check_not_null(po_lines, "po_lines", "part_id"))

    # Allowed values
    results.append(check_allowed_values(suppliers, "suppliers", "status", {"Active", "Inactive"}, severity="WARN"))
    results.append(check_allowed_values(parts, "parts", "is_active", {0, 1, "0", "1"}, severity="WARN"))
    results.append(check_allowed_values(purchase_orders, "purchase_orders", "status", {"Open", "Closed", "Cancelled"}, severity="WARN"))
    results.append(check_allowed_values(purchase_orders, "purchase_orders", "currency", {"USD", "EUR", "GBP", "JPY", "CAD", "AUD"}, severity="WARN"))

    # Numeric checks
    results.append(check_numeric_min(po_lines, "po_lines", "qty", 0.000001))
    results.append(check_numeric_min(po_lines, "po_lines", "unit_price", 0.0))
    results.append(check_numeric_min(purchase_orders, "purchase_orders", "total_amount", 0.0, severity="WARN"))

    # FK checks
    results.append(check_fk_exists(purchase_orders, suppliers, "purchase_orders", "supplier_id", "supplier_id"))
    results.append(check_fk_exists(po_lines, purchase_orders, "po_lines", "po_id", "po_id"))
    results.append(check_fk_exists(po_lines, parts, "po_lines", "part_id", "part_id"))

    # Math + reconcile
    results.append(check_line_amount_math(po_lines))
    results.append(check_po_totals_reconcile(purchase_orders, po_lines, severity="WARN"))

    return results


def write_reports(results: list[CheckResult], out_dir: str | Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "validation_report.json"
    csv_path = out_dir / "validation_report.csv"

    payload = results_to_json(results)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    df = results_to_dataframe(results)
    df.to_csv(csv_path, index=False)

    summary = {
        "total_checks": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "critical_failed": sum(1 for r in results if (not r.passed and r.severity == "CRITICAL")),
        "json_report": str(json_path),
        "csv_report": str(csv_path),
    }
    return summary


def setup_logging(log_dir: str | Path) -> None:
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "validation.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run data quality validation on CSV datasets.")
    parser.add_argument("--data-dir", default="data", help="Folder containing input CSVs")
    parser.add_argument("--out-dir", default="reports", help="Folder to write reports")
    parser.add_argument("--log-dir", default="logs", help="Folder to write logs")
    args = parser.parse_args()

    setup_logging(args.log_dir)

    results = run_all_checks(args.data_dir)
    summary = write_reports(results, args.out_dir)

    print(json.dumps(summary, indent=2))
    
    critical_failed = any((not r.passed) and (r.severity == "CRITICAL") for r in results)
    return 2 if critical_failed else 0


if __name__ == "__main__":
    sys.exit(main())
