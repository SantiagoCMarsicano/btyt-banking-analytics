import pandas as pd

from scripts.config import RAW_DATA_DIR


def load_master_data():
    branches = pd.read_csv(RAW_DATA_DIR / "branches.csv")
    products = pd.read_csv(RAW_DATA_DIR / "products.csv")
    campaigns = pd.read_csv(RAW_DATA_DIR / "campaigns.csv")

    return branches, products, campaigns


if __name__ == "__main__":
    branches, products, campaigns = load_master_data()

    print("=== BTYT MASTER DATA TEST ===")
    print(f"Branches: {len(branches)}")
    print(f"Products: {len(products)}")
    print(f"Campaigns: {len(campaigns)}")
    
    