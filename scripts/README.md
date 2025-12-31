# Data Quality Check Automation

A command-line tool for validating procurement CSV data with comprehensive data quality checks.

## Quick Start

### Generate Sample Data
```bash
python -m scripts.data_generator
```
Creates sample CSV files in `data/` directory with intentional quality issues for testing.

### Run Validation
```bash
python -m scripts.run_validation --data-dir data --out-dir reports --log-dir logs
```

**Arguments:**
- `--data-dir` (default: `data`) - Directory containing input CSV files
- `--out-dir` (default: `reports`) - Directory to write validation reports
- `--log-dir` (default: `logs`) - Directory to write logs

**Exit Codes:**
- `0` - All checks passed
- `1` - Critical failures found
- `2` - Validation execution error

## Output

The tool generates:
1. **validation_report.json** - Machine-readable report with detailed check results
2. **validation_report.csv** - Spreadsheet-friendly summary
3. **logs/validation.log** - Execution logs

## Data Requirements

Input CSVs must include:

### suppliers.csv
- supplier_id (PK)
- supplier_name
- status (must be "Active" or "Inactive")
- country

### parts.csv
- part_id (PK)
- part_name
- part_type
- uom
- is_active (must be 0 or 1)

### purchase_orders.csv
- po_id (PK)
- supplier_id (FK → suppliers)
- po_date
- currency (must be USD, EUR, GBP, JPY, CAD, or AUD)
- total_amount (must match sum of po_lines)
- status (must be "Open", "Closed", or "Cancelled")

### po_lines.csv
- po_line_id (PK)
- po_id (FK → purchase_orders)
- part_id (FK → parts)
- qty (must be > 0)
- unit_price (must be ≥ 0)
- line_amount (must equal qty × unit_price)

## Checks Performed

### Schema Validation
- Required columns present in each table

### Primary Key Checks
- No duplicate IDs
- IDs not null

### Foreign Key Checks
- supplier_id in purchase_orders exists in suppliers
- po_id in po_lines exists in purchase_orders
- part_id in po_lines exists in parts

### Allowed Values
- supplier status: Active, Inactive
- parts is_active: 0, 1
- purchase_orders status: Open, Closed, Cancelled
- currency: USD, EUR, GBP, JPY, CAD, AUD

### Numeric Constraints
- qty > 0
- unit_price ≥ 0
- total_amount ≥ 0 (warning level)

### Business Logic
- **line_amount_math**: qty × unit_price = line_amount
- **po_totals_reconcile**: sum(po_lines.line_amount) = purchase_orders.total_amount

## Module Structure

```
scripts/
├── __init__.py              # Package marker
├── run_validation.py        # CLI entry point & validation engine
├── data_generator.py        # Sample data generation
└── README.md               # This file
```

## Example Usage

### Validate custom data directory
```bash
python -m scripts.run_validation --data-dir ./my_data --out-dir ./my_reports
```

### Generate data and validate
```bash
python -m scripts.data_generator
python -m scripts.run_validation
```

### Check logs
```bash
cat logs/validation.log
```

## Return Value Examples

**All checks passed:**
```json
{
  "total_checks": 27,
  "passed": 27,
  "failed": 0,
  "critical_failed": 0,
  "json_report": "reports/validation_report.json",
  "csv_report": "reports/validation_report.csv"
}
```

**Some checks failed:**
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

## Check Severity Levels

- **CRITICAL**: Data integrity violations (must be fixed)
- **WARN**: Quality issues that should be reviewed

Report exit code is 1 if any CRITICAL checks fail.
