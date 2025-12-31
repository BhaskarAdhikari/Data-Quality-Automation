from pathlib import Path
import pandas as pd
import numpy as np


def main(out_dir: str | Path = "data") -> None:
    """Generate synthetic procurement data with intentional quality issues."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # === Suppliers ===
    suppliers_data = {
        "supplier_id": [1, 2, 3, 4, 5],
        "supplier_name": ["ACME Corp", "XYZ Ltd", None, "Delta Inc", "Epsilon AG"],
        "status": ["Active", "Active", "Inactive", "Unknown", "Active"],  # 'Unknown' is invalid
        "country": ["USA", "UK", "Germany", "Canada", "France"],
    }
    suppliers_df = pd.DataFrame(suppliers_data)
    suppliers_df.to_csv(out_dir / "suppliers.csv", index=False)

    # === Parts ===
    parts_data = {
        "part_id": [101, 102, 103, 101, 105],  # 101 is duplicated
        "part_name": ["Widget A", "Widget B", "Widget C", "Widget D", None],
        "part_type": ["Electronic", "Mechanical", "Electrical", "Electronic", "Mechanical"],
        "uom": ["Each", "Each", "Box", "Each", "Box"],
        "is_active": [1, 0, 1, 1, "invalid"],  # 'invalid' is not 0 or 1
    }
    parts_df = pd.DataFrame(parts_data)
    parts_df.to_csv(out_dir / "parts.csv", index=False)

    # === Purchase Orders ===
    po_data = {
        "po_id": [1001, 1002, 1003, 1004, 1005],
        "supplier_id": [1, 2, 999, None, 5],  # 999 doesn't exist, None is invalid
        "po_date": ["2024-01-15", "2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19"],
        "currency": ["USD", "EUR", "XXX", "USD", "GBP"],  # 'XXX' is invalid
        "total_amount": [5000.50, 3200.75, -100.00, 0.00, 12500.00],  # negative and zero might be invalid per business logic
        "status": ["Open", "Closed", "Cancelled", "Invalid", "Open"],  # 'Invalid' is not allowed
    }
    po_df = pd.DataFrame(po_data)
    po_df.to_csv(out_dir / "purchase_orders.csv", index=False)

    # === PO Lines ===
    po_lines_data = {
        "po_line_id": [5001, 5002, 5003, 5004, 5005, 5006],
        "po_id": [1001, 1001, 1002, 1003, 1004, 999],  # 999 doesn't exist
        "part_id": [101, 102, 102, 103, 105, 101],
        "qty": [10, 5, 3, -2, 0, 1],  # -2 and 0 fail numeric_min check
        "unit_price": [50.00, 100.00, 200.00, 150.00, 50.00, 80.00],
        "line_amount": [500.00, 500.00, 605.00, 300.00, 0.00, 80.00],  # 605.00 fails line_amount_math (5*200=1000)
    }
    po_lines_df = pd.DataFrame(po_lines_data)
    po_lines_df.to_csv(out_dir / "po_lines.csv", index=False)


if __name__ == "__main__":
    main()
