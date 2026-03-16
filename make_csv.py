"""Merge NOC 2021 structure + wages + Eloundou scores + COPS projections into occupations.csv."""

import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")

CODE_COL = "Code - NOC 2021 V1.0"


def load_noc_structure() -> pd.DataFrame:
    """Load NOC structure and extract 5-digit unit groups with hierarchy info."""
    df = pd.read_csv(DATA_DIR / "noc_structure.csv")

    # Only keep 5-digit unit groups (Level 5)
    units = df[df["Level"] == 5].copy()

    # Zero-pad codes to 5 digits
    units["noc_code"] = units[CODE_COL].astype(str).str.zfill(5)

    # Extract hierarchy from the 5-digit code
    units["broad_category"] = units["noc_code"].str[0]
    units["teer"] = units["noc_code"].str[1]
    units["major_group"] = units["noc_code"].str[:2]
    units["sub_major_group"] = units["noc_code"].str[:3]
    units["minor_group"] = units["noc_code"].str[:4]

    units = units.rename(columns={
        "Class title": "title",
        "Class definition": "definition",
    })

    # Map broad category names (Level 1 = 1-digit broad categories)
    broad_cats = df[df["Level"] == 1].set_index(CODE_COL)["Class title"].to_dict()
    units["broad_category_name"] = units["broad_category"].astype(int).map(broad_cats)

    return units[["noc_code", "title", "definition", "broad_category", "broad_category_name",
                   "teer", "major_group", "sub_major_group", "minor_group"]].reset_index(drop=True)


def load_wages() -> pd.DataFrame:
    """Load wages CSV, filter to national level, convert to annual."""
    df = pd.read_csv(DATA_DIR / "wages_2025.csv", encoding="utf-8-sig", low_memory=False)

    # Filter to national level only
    nat = df[df["prov"] == "NAT"].copy()

    # Extract 5-digit NOC code from NOC_00010 format
    nat["noc_code"] = nat["NOC_CNP"].str.replace("NOC_", "").str.lstrip("0").str.zfill(5)

    # Annual_Wage_Flag = 1 means already annual, 0 means hourly
    nat["annual_flag"] = nat["Annual_Wage_Flag_Salaire_annuel"]

    wage_cols = {
        "Low_Wage_Salaire_Minium": "wage_low",
        "Median_Wage_Salaire_Median": "wage_median",
        "High_Wage_Salaire_Maximal": "wage_high",
        "Average_Wage_Salaire_Moyen": "wage_avg",
    }
    nat = nat.rename(columns=wage_cols)

    # Convert hourly wages to annual (2,080 hours)
    hourly_mask = nat["annual_flag"] == 0
    for col in wage_cols.values():
        nat.loc[hourly_mask, col] = nat.loc[hourly_mask, col] * 2080

    # Round to nearest dollar
    for col in wage_cols.values():
        nat[col] = nat[col].round(0)

    return nat[["noc_code", "wage_low", "wage_median", "wage_high", "wage_avg"]].reset_index(drop=True)


def load_eloundou() -> pd.DataFrame:
    """Load crosswalked Eloundou LLM exposure scores (NOC 2021)."""
    path = DATA_DIR / "eloundou_noc2021.csv"
    if not path.exists():
        print("  WARNING: eloundou_noc2021.csv not found — run crosswalk.py first")
        return pd.DataFrame(columns=["noc_code", "alpha", "beta", "gamma"])
    return pd.read_csv(path, dtype={"noc_code": str})


def load_cops() -> pd.DataFrame:
    """Load COPS projected conditions, employment counts, and employment growth."""
    # Projected conditions
    cond = pd.read_csv(DATA_DIR / "cops_projected_conditions.csv", encoding="latin-1")
    cond = cond[cond["Code"].str.match(r"^\d{5}$", na=False)].copy()
    cond["noc_code"] = cond["Code"].str.zfill(5)
    cond = cond.rename(columns={"Future_Labour_Market_Conditions": "outlook"})
    cond = cond[["noc_code", "outlook"]]

    # Employment counts + supply/demand from COPS summary
    summary = pd.read_csv(DATA_DIR / "cops_summary.csv", encoding="latin-1")
    summary = summary[summary["Code"].str.match(r"^\d{5}$", na=False)].copy()
    summary["noc_code"] = summary["Code"].str.zfill(5)
    summary = summary.rename(columns={
        "Employment_emploi_2023": "employment",
        "Total_Job_Openings_Perspective_d'emploi": "job_openings",
        "Job_Seekers_Chercheurs_emploi": "job_seekers_raw",
        "Immigration": "immigration",
        "School_Leavers_Sortants_scolaires": "school_leavers",
        "Retirements_retraites": "retirements",
    })
    # job_seekers may have commas in the number
    summary["job_seekers"] = pd.to_numeric(
        summary["job_seekers_raw"].astype(str).str.replace(",", ""), errors="coerce"
    )
    # Supply/demand ratio (seekers per opening, >1 = surplus, <1 = shortage)
    summary["supply_demand_ratio"] = (summary["job_seekers"] / summary["job_openings"]).round(3)
    # Immigration share of total seekers
    summary["immigration_share"] = (summary["immigration"] / summary["job_seekers"]).round(3)

    summary = summary[["noc_code", "employment", "job_openings", "job_seekers",
                        "immigration", "school_leavers", "retirements",
                        "supply_demand_ratio", "immigration_share"]]

    # Employment growth — year-by-year + average
    growth = pd.read_csv(DATA_DIR / "cops_employment_growth.csv", encoding="latin-1")
    growth = growth[growth["Code"].str.match(r"^\d{5}$", na=False)].copy()
    growth["noc_code"] = growth["Code"].str.zfill(5)
    year_cols = [str(y) for y in range(2024, 2034)]
    growth["growth_trend"] = growth[year_cols].mean(axis=1).round(0)
    # Store year-by-year as a JSON string for later use
    growth["growth_by_year"] = growth[year_cols].apply(
        lambda row: [int(v) if pd.notna(v) else 0 for v in row], axis=1
    ).apply(str)
    growth = growth[["noc_code", "growth_trend", "growth_by_year"]]

    return cond.merge(summary, on="noc_code", how="outer").merge(growth, on="noc_code", how="outer")


def derive_timeline(row: pd.Series) -> str:
    """Derive AI impact time horizon from Eloundou scores + COPS outlook.

    Logic:
    - alpha = LLM alone (current capabilities) → 0-2yr signal
    - beta = LLM + some tools → 2-3yr signal
    - gamma = LLM + full tooling → 3+yr signal

    Primary: which tier shows the biggest jump in exposure?
    COPS modifier: surplus risk shifts earlier, shortage risk shifts later.
    """
    alpha = row.get("alpha", 0) or 0
    beta = row.get("beta", 0) or 0
    gamma = row.get("gamma", 0) or 0
    outlook = row.get("outlook", "Balance") or "Balance"

    # If alpha is already high, impact is near-term
    # If the big jump is alpha→beta, medium-term (needs tools)
    # If the big jump is beta→gamma, long-term (needs major tools)
    if alpha >= 0.3:
        base = "0-2yr"
    elif beta - alpha > gamma - beta and beta >= 0.3:
        base = "2-3yr"
    elif alpha >= 0.15 or beta >= 0.25:
        base = "2-3yr"
    else:
        base = "3+yr"

    # COPS modifier
    buckets = ["0-2yr", "2-3yr", "3+yr"]
    idx = buckets.index(base)

    if outlook in ("Strong risk of Surplus", "Moderate risk of Surplus"):
        idx = max(0, idx - 1)  # Shift earlier
    elif outlook in ("Strong risk of Shortage", "Moderate risk of Shortage"):
        idx = min(2, idx + 1)  # Shift later

    return buckets[idx]


def main() -> None:
    print("Loading NOC structure...")
    noc = load_noc_structure()
    print(f"  {len(noc)} unit groups loaded")

    print("Loading wages...")
    wages = load_wages()
    print(f"  {len(wages)} national wage records loaded")

    print("Loading Eloundou LLM exposure scores...")
    eloundou = load_eloundou()
    print(f"  {len(eloundou)} NOC codes with scores")

    print("Loading COPS projections...")
    cops = load_cops()
    print(f"  {len(cops)} NOC codes with outlook data")

    print("Merging...")
    merged = noc.merge(wages, on="noc_code", how="left")
    merged = merged.merge(eloundou, on="noc_code", how="left")
    merged = merged.merge(cops, on="noc_code", how="left")

    # Fill missing Eloundou scores with median
    for col in ["alpha", "beta", "gamma"]:
        median_val = merged[col].median()
        merged[col] = merged[col].fillna(median_val).round(4)

    # Derive timeline
    merged["timeline"] = merged.apply(derive_timeline, axis=1)

    print(f"  {len(merged)} rows after merge")

    missing_wages = merged["wage_median"].isna().sum()
    if missing_wages:
        print(f"  WARNING: {missing_wages} occupations missing median wage")

    out = Path("occupations.csv")
    merged.to_csv(out, index=False)
    print(f"\nSaved to {out} ({len(merged)} rows)")

    # Stats
    print(f"\nTimeline distribution:")
    print(merged["timeline"].value_counts().to_string())
    print(f"\nOutlook distribution:")
    print(merged["outlook"].value_counts().to_string())
    print(f"\nEloundou score ranges:")
    print(f"  Alpha: {merged['alpha'].min():.3f} - {merged['alpha'].max():.3f}")
    print(f"  Beta:  {merged['beta'].min():.3f} - {merged['beta'].max():.3f}")
    print(f"  Gamma: {merged['gamma'].min():.3f} - {merged['gamma'].max():.3f}")

    # Spot-check examples
    print(f"\nSpot-check:")
    examples = {"14111": "Data entry clerks", "21232": "Software developers",
                "72200": "Electricians", "11100": "Financial auditors/accountants",
                "73200": "Residential framers", "41200": "University professors"}
    for code, name in examples.items():
        row = merged[merged["noc_code"] == code]
        if len(row):
            r = row.iloc[0]
            print(f"  {code} {name}: α={r['alpha']:.3f} β={r['beta']:.3f} γ={r['gamma']:.3f} "
                  f"outlook={r['outlook']} → {r['timeline']}")


if __name__ == "__main__":
    main()
