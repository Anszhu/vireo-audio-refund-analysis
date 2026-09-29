"""Load raw files exactly as supplied. Nothing is modified on disk."""
from pathlib import Path
import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
FILES = ["tickets.csv", "agents.csv", "orders.csv", "customers.csv", "products.csv"]


def load_raw(raw_dir=RAW_DIR):
    raw_dir = Path(raw_dir)
    missing = [f for f in FILES if not (raw_dir / f).exists()]
    if missing:
        raise FileNotFoundError(f"Missing input files in {raw_dir}: {missing}. See data/README.md")
    # tickets read as strings so nothing (IDs, blanks, amounts) is silently coerced
    tickets = pd.read_csv(raw_dir / "tickets.csv", dtype=str, keep_default_na=True)
    agents = pd.read_csv(raw_dir / "agents.csv", dtype=str)
    orders = pd.read_csv(raw_dir / "orders.csv", dtype={"order_id": str, "customer_id": str})
    customers = pd.read_csv(raw_dir / "customers.csv", dtype=str)
    products = pd.read_csv(raw_dir / "products.csv")
    return dict(tickets=tickets, agents=agents, orders=orders, customers=customers, products=products)
