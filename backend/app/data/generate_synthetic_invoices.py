import argparse
import os
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List

# Ensure backend root is in sys.path when executed directly
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy import delete, func, select
from app.database import SessionLocal, engine
from app.models import Invoice

# --- Constants & Realistic FMCG Data ---

FMCG_HSN_CODES = [
    ("1905", "Biscuits, Bread, Pastries, Cakes"),
    ("0902", "Tea & Herbal Infusions"),
    ("3401", "Soaps, Detergents, Washing Powders"),
    ("2106", "Food Preparations & Health Supplements"),
    ("0402", "Milk Powder & Condensed Dairy Products"),
    ("3306", "Toothpastes & Oral Hygiene"),
    ("1511", "Refined Edible Cooking Oils"),
    ("2202", "Packaged Fruit Juices & Carbonated Beverages"),
    ("3305", "Shampoos & Hair Care Products"),
    ("1704", "Confectionery & Sugar Candies"),
]

# 18 FMCG Retailers & Kirana Distributors across Indian states
RETAILERS = [
    {
        "id": "CUST-DELHI-KIRANA-01",
        "name": "Aggarwal Super Store",
        "gst_state": "07",
        "pan": "AABCA1234F",
        "city": "New Delhi",
    },
    {
        "id": "CUST-MUMBAI-RETAIL-02",
        "name": "Shree Balaji Traders",
        "gst_state": "27",
        "pan": "BCEPD5678K",
        "city": "Mumbai",
    },
    {
        "id": "CUST-BLR-MART-03",
        "name": "Lakshmi Daily Needs",
        "gst_state": "29",
        "pan": "CLMPR9012L",
        "city": "Bengaluru",
    },
    {
        "id": "CUST-HYD-PROV-04",
        "name": "Sri Venkateshwara Provisions",
        "gst_state": "36",
        "pan": "DGKPS3456M",
        "city": "Hyderabad",
    },
    {
        "id": "CUST-CHENNAI-SUP-05",
        "name": "Murugan General Stores",
        "gst_state": "33",
        "pan": "EFLPT7890N",
        "city": "Chennai",
    },
    {
        "id": "CUST-PUNE-BAZAR-06",
        "name": "Ganesh Kirana Bhandar",
        "gst_state": "27",
        "pan": "FHMPU2345P",
        "city": "Pune",
    },
    {
        "id": "CUST-AHD-TRADE-07",
        "name": "Patel Consumer Goods",
        "gst_state": "24",
        "pan": "GINQV6789Q",
        "city": "Ahmedabad",
    },
    {
        "id": "CUST-KOL-MARKET-08",
        "name": "Maa Durga Grocery",
        "gst_state": "19",
        "pan": "HJNRW0123R",
        "city": "Kolkata",
    },
    {
        "id": "CUST-JAIPUR-FMCG-09",
        "name": "Khandelwal Enterprises",
        "gst_state": "08",
        "pan": "IKOSX4567S",
        "city": "Jaipur",
    },
    {
        "id": "CUST-LKO-WHOLE-10",
        "name": "Awadh Traders",
        "gst_state": "09",
        "pan": "JLPTY8901T",
        "city": "Lucknow",
    },
    {
        "id": "CUST-CHD-RETAIL-11",
        "name": "City Prime Mart",
        "gst_state": "04",
        "pan": "KMQUZ2345U",
        "city": "Chandigarh",
    },
    {
        "id": "CUST-INDORE-PROV-12",
        "name": "Malwa Daily Needs",
        "gst_state": "23",
        "pan": "LNVA16789V",
        "city": "Indore",
    },
    {
        "id": "CUST-SURAT-KIRANA-13",
        "name": "Ambica Super Market",
        "gst_state": "24",
        "pan": "MOWB20123W",
        "city": "Surat",
    },
    {
        "id": "CUST-NAGPUR-SUP-14",
        "name": "Vidarbha FMCG Hub",
        "gst_state": "27",
        "pan": "NPXC34567X",
        "city": "Nagpur",
    },
    {
        "id": "CUST-PATNA-STORE-15",
        "name": "Magadh Retailers",
        "gst_state": "10",
        "pan": "OQYD48901Y",
        "city": "Patna",
    },
    {
        "id": "CUST-KOCHI-TRADE-16",
        "name": "Cochin Express Mart",
        "gst_state": "32",
        "pan": "PRZE52345Z",
        "city": "Kochi",
    },
    {
        "id": "CUST-COIMBATORE-17",
        "name": "Kongu Hyper Provision",
        "gst_state": "33",
        "pan": "QSAF66789A",
        "city": "Coimbatore",
    },
    {
        "id": "CUST-VARANASI-18",
        "name": "Kashi Kirana Mart",
        "gst_state": "09",
        "pan": "RTBG70123B",
        "city": "Varanasi",
    },
]


def format_gstin(state_code: str, pan: str, entity_num: int = 1) -> str:
    """Format realistic 15-character Indian GSTIN."""
    # 2 digits state + 10 chars PAN + 1 digit entity ('1') + 'Z' + 1 checksum char
    checksum_char = random.choice("123456789ABCDEFGHJKLMNPQRSTUVWXYZ")
    return f"{state_code}{pan}{entity_num}Z{checksum_char}"


def generate_invoices() -> List[Dict]:
    """Generate 60 realistic FMCG B2B invoice records with specified distribution."""
    random.seed(42)  # Deterministic seed for reproducible testing
    today = date.today()

    # Distribution out of 60:
    # ~60% Paid (36)
    # ~25% Overdue (15) [10-35 days overdue]
    # ~10% Disputed (6)
    # ~5% Severely Overdue (3) [45+ days overdue]
    target_specs = (
        [("paid", False)] * 36
        + [("overdue", False)] * 15
        + [("disputed", False)] * 6
        + [("overdue", True)] * 3  # Severely overdue
    )

    random.shuffle(target_specs)

    records = []
    invoice_seq = 1001

    for idx, (status, is_severe) in enumerate(target_specs, start=1):
        retailer = RETAILERS[(idx - 1) % len(RETAILERS)]
        hsn_code, _ = random.choice(FMCG_HSN_CODES)
        credit_terms = random.choice(["net_30", "net_45"])
        terms_days = 30 if credit_terms == "net_30" else 45

        # Amounts between ₹15,000 and ₹4,00,000 (rounded to hundreds)
        raw_amount = random.uniform(15000, 400000)
        amount = Decimal(str(round(raw_amount, -2)))

        gstin = format_gstin(retailer["gst_state"], retailer["pan"])
        inv_num = f"INV-2024-FMCG-{invoice_seq}"
        invoice_seq += 1

        if is_severe:
            # Severely overdue: due date is 46 to 75 days in the past
            days_overdue = random.randint(46, 75)
            due_date = today - timedelta(days=days_overdue)
        elif status == "overdue":
            # Normal overdue: due date is 5 to 35 days in the past
            days_overdue = random.randint(5, 35)
            due_date = today - timedelta(days=days_overdue)
        elif status == "disputed":
            # Disputed: due date is 10 to 40 days in the past or upcoming
            days_diff = random.randint(-15, 30)
            due_date = today - timedelta(days=days_diff)
        else:
            # Paid: due date was 10 to 60 days ago
            days_ago = random.randint(10, 60)
            due_date = today - timedelta(days=days_ago)

        records.append(
            {
                "customer_id": retailer["id"],
                "invoice_number": inv_num,
                "gst_number": gstin,
                "hsn_code": hsn_code,
                "amount": amount,
                "due_date": due_date,
                "credit_terms": credit_terms,
                "status": status,
            }
        )

    return records


def seed_database(reset: bool = False):
    """Seed PostgreSQL database with 60 synthetic FMCG invoices."""
    db = SessionLocal()
    try:
        existing_count = db.scalar(select(func.count(Invoice.id))) or 0
        if existing_count > 0:
            if not reset:
                print(
                    f"\n[WARNING] Database already contains {existing_count} invoices."
                )
                print("Use '--reset' flag to truncate and re-seed.")
                return
            else:
                print(f"[RESET] Truncating existing {existing_count} invoices...")
                db.execute(delete(Invoice))
                db.commit()

        print("[SEEDING] Generating 60 FMCG B2B invoices...")
        data = generate_invoices()
        invoices = [Invoice(**row) for row in data]
        db.add_all(invoices)
        db.commit()

        # Fetch and print summary counts
        print("\n" + "=" * 50)
        print(" RECOUP FMCG SYNTHETIC INVOICE SEEDING COMPLETE")
        print("=" * 50)
        print(f"Total Invoices Created : {len(invoices)}")
        print(f"Unique Customers       : {len(set(r['customer_id'] for r in data))}")
        print("-" * 50)
        print("Status Breakdown:")

        status_counts = {}
        for row in data:
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1

        for stat, count in sorted(status_counts.items()):
            pct = (count / len(invoices)) * 100
            print(f"  - {stat.upper():<10}: {count:>3} invoices ({pct:.1f}%)")

        # Check severely overdue count
        severe_count = sum(
            1
            for row in data
            if row["status"] == "overdue"
            and (date.today() - row["due_date"]).days >= 45
        )
        print(
            f"  * of which severely overdue (>= 45 days late): {severe_count} invoices"
        )
        print("=" * 50 + "\n")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Seed Recoup database with 60 FMCG B2B invoices."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Truncate existing invoices table and re-seed from scratch.",
    )
    args = parser.parse_args()
    seed_database(reset=args.reset)


if __name__ == "__main__":
    main()
