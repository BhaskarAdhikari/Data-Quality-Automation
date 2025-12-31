# Data Quality Check Automation

A production-ready command-line tool for validating procurement CSV data with comprehensive data quality checks. Detects schema violations, primary key duplicates, foreign key breaks, null values, invalid domains, and business logic inconsistencies.

## Features

✓ **27 Automated Checks** - Schema, primary keys, foreign keys, nulls, domains, numeric ranges, line-level math, and reconciliation  
✓ **Severity Levels** - CRITICAL (blocks progress) and WARN (informational)  
✓ **Multiple Report Formats** - JSON (detailed), CSV (spreadsheet-friendly), logs  
✓ **Fast Execution** - Validates 1000s of rows in seconds  
✓ **Sample Failures** - Each check includes up to 5 failed row examples for debugging  

## Quick Start

### 1. Install Dependencies
```bash
pip install pandas numpy
```

### 2. Generate Sample Data (Optional)
```bash
python -m scripts.data_generator
```
Creates 4 CSVs with intentional quality issues for testing.

### 3. Run Validation
```bash
python -m scripts.run_validation --data-dir data --out-dir reports --log-dir logs
```

### Expected Output
```json
{
  "total_checks": 27,
  "passed": 15,
  "failed": 12,
  "critical_failed": 6,
  "json_report": "reports/validation_report.json",
  "csv_report": "reports/validation_report.csv"
}
```

## Usage

### Command-Line Arguments
```bash
python -m scripts.run_validation \
  --data-dir data \          # Directory containing input CSVs (default: "data")
  --out-dir reports \         # Directory to write reports (default: "reports")
  --log-dir logs              # Directory to write logs (default: "logs")
```

### Examples

**Validate with default paths**
```bash
python -m scripts.run_validation
```

**Custom input/output directories**
```bash
python -m scripts.run_validation --data-dir ./my_data --out-dir ./my_reports
```

**View logs**
```bash
tail -f logs/validation.log
```

**Check exit code programmatically**
```bash
python -m scripts.run_validation
if [ $? -eq 0 ]; then echo "All checks passed"; else echo "Failures detected"; fi
```

## Data Requirements

### Input CSV Files
Place all 4 CSVs in the `--data-dir` directory:

#### suppliers.csv
```
supplier_id | supplier_name | status      | country
1001        | ACME Corp     | ACTIVE      | US
1002        | XYZ Ltd       | INACTIVE    | UK
```
**Required Columns**: `supplier_id`, `supplier_name`, `status`, `country`  
**Primary Key**: `supplier_id`  
**Status Values**: ACTIVE, INACTIVE, BLOCKED

#### parts.csv
```
part_id | part_name   | part_type | uom  | is_active
20001   | Widget A    | RAW       | EA   | 1
20002   | Widget B    | FINISHED  | KG   | 0
```
**Required Columns**: `part_id`, `part_name`, `part_type`, `uom`, `is_active`  
**Primary Key**: `part_id`  
**is_active Values**: 0 or 1

#### purchase_orders.csv
```
po_id  | supplier_id | po_date    | currency | total_amount | status
500001 | 1001        | 2024-01-15 | USD      | 5000.50      | OPEN
500002 | 1002        | 2024-01-16 | EUR      | 3200.75      | CLOSED
```
**Required Columns**: `po_id`, `supplier_id`, `po_date`, `currency`, `total_amount`, `status`  
**Primary Key**: `po_id`  
**Foreign Key**: `supplier_id` → suppliers.supplier_id  
**Status Values**: OPEN, APPROVED, CLOSED, CANCELLED  
**Currency Values**: USD, EUR, GBP, CAD, JPY, INR, AUD  
**total_amount**: Must be ≥ 0 and equal to sum of line amounts for the PO

#### po_lines.csv
```
po_line_id | po_id | part_id | qty  | unit_price | line_amount
9000001    | 500001| 20001   | 10   | 50.00      | 500.00
9000002    | 500001| 20002   | 5    | 100.00     | 500.00
```
**Required Columns**: `po_line_id`, `po_id`, `part_id`, `qty`, `unit_price`, `line_amount`  
**Primary Key**: `po_line_id`  
**Foreign Keys**: `po_id` → purchase_orders.po_id, `part_id` → parts.part_id  
**qty**: Must be > 0  
**unit_price**: Must be ≥ 0  
**line_amount**: Must equal qty × unit_price (within 0.01 tolerance)

## Validation Checks

### Schema Checks
| Check | Severity | Details |
|-------|----------|---------|
| `required_columns` | CRITICAL | All expected columns must be present |

### Primary Key Checks
| Check | Severity | Details |
|-------|----------|---------|
| `primary_key_unique` | CRITICAL | No duplicate IDs in each table |
| `not_null:{id_column}` | CRITICAL | All IDs must be non-null |

### Foreign Key Checks
| Check | Severity | Details |
|-------|----------|---------|
| `fk_exists:supplier_id->supplier_id` | CRITICAL | supplier_id in POs must exist in suppliers |
| `fk_exists:po_id->po_id` | CRITICAL | po_id in lines must exist in purchase_orders |
| `fk_exists:part_id->part_id` | CRITICAL | part_id in lines must exist in parts |

### Domain & Null Checks
| Check | Severity | Details |
|-------|----------|---------|
| `not_null:{col}` | CRITICAL | Required fields cannot be null |
| `allowed_values:status` | WARN | Status must be in allowed set |
| `allowed_values:currency` | WARN | Currency must be in allowed set |
| `allowed_values:is_active` | WARN | is_active must be 0 or 1 |

### Numeric Checks
| Check | Severity | Details |
|-------|----------|---------|
| `numeric_min:qty` | CRITICAL | qty must be > 0 |
| `numeric_min:unit_price` | CRITICAL | unit_price must be ≥ 0 |
| `numeric_min:total_amount` | WARN | total_amount should be ≥ 0 |

### Business Logic Checks
| Check | Severity | Details |
|-------|----------|---------|
| `line_amount_math` | CRITICAL | line_amount must equal qty × unit_price |
| `po_totals_reconcile` | WARN | PO total must equal sum of line amounts |

## Output Reports

### validation_report.json
Machine-readable report with per-check details:
```json
[
  {
    "check_name": "required_columns",
    "table": "suppliers",
    "severity": "CRITICAL",
    "passed": true,
    "failed_count": 0,
    "sample_failures": []
  },
  {
    "check_name": "primary_key_unique",
    "table": "suppliers",
    "severity": "CRITICAL",
    "passed": false,
    "failed_count": 3,
    "sample_failures": [
      {"supplier_id": 1001},
      {"supplier_id": 1002}
    ]
  }
]
```

### validation_report.csv
Spreadsheet-friendly summary (import into Excel/Google Sheets):
```
check_name,table,severity,passed,failed_count,sample_failures
required_columns,suppliers,CRITICAL,True,0,[]
primary_key_unique,suppliers,CRITICAL,False,3,"[{'supplier_id': 1001}]"
```

### logs/validation.log
Timestamped execution log:
```
2025-01-01 10:30:45,123 INFO Loading CSVs from data/raw
2025-01-01 10:30:45,456 INFO Running 27 checks...
2025-01-01 10:30:46,789 INFO Results written to reports/
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed (no CRITICAL failures) |
| `1` | One or more CRITICAL checks failed |
| `2` | Validation execution error (missing files, bad data format, etc.) |

Use in scripts:
```bash
python -m scripts.run_validation
case $? in
  0) echo "✓ Data quality OK" ;;
  1) echo "✗ Critical failures found" ;;
  2) echo "✗ Execution error" ;;
esac
```

## Module Structure

```
Automation/
├── scripts/
│   ├── __init__.py              # Package marker
│   ├── run_validation.py        # Main CLI entry point (275 lines)
│   │                             # - argparse configuration
│   │                             # - All 27 check functions
│   │                             # - Report generation
│   ├── data_generator.py        # Synthetic test data generator
│   └── README.md                # Module documentation
├── data/                        # Input CSVs directory
│   ├── suppliers.csv
│   ├── parts.csv
│   ├── purchase_orders.csv
│   └── po_lines.csv
├── reports/                     # Output reports
│   ├── validation_report.json
│   └── validation_report.csv
├── logs/                        # Execution logs
│   └── validation.log
├── DQ Check Automation.ipynb    # Original Jupyter notebook (reference)
└── README.md                    # This file
```

## Development

### Run Tests
```bash
# Generate fresh test data
python -m scripts.data_generator

# Run validation
python -m scripts.run_validation --data-dir data --out-dir reports --log-dir logs

# Check results
cat reports/validation_report.json | python -m json.tool
```

### Extend Validation
To add new checks, edit `scripts/run_validation.py`:

1. Define new check function:
```python
def check_my_custom_validation(df: pd.DataFrame, table: str) -> CheckResult:
    # Your validation logic
    bad_mask = ... 
    return CheckResult(
        check_name="my_check",
        table=table,
        severity="CRITICAL",
        passed=bad_mask.sum() == 0,
        failed_count=int(bad_mask.sum()),
        sample_failures=_sample_rows(df, bad_mask, [...])
    )
```

2. Add to `run_all_checks()`:
```python
results.append(check_my_custom_validation(my_df, "my_table"))
```

3. Re-run validation to test.

## License

MIT

## Support

For issues, questions, or feature requests, open an issue on GitHub.
