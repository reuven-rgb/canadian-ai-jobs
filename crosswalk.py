"""Map Eloundou et al. LLM exposure scores from US SOC to Canadian NOC 2021.

Chain: O*NET-SOC → SOC 2018 → NOC 2016 → NOC 2021
"""

import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")


def load_eloundou() -> pd.DataFrame:
    """Load Eloundou scores, normalize SOC codes to 6-digit format."""
    df = pd.read_csv(DATA_DIR / "eloundou_scores.csv")
    # O*NET-SOC codes like "11-1011.00" → SOC 2018 "11-1011"
    df["soc_code"] = df["O*NET-SOC Code"].str.replace(r"\.\d+$", "", regex=True)
    # Average duplicate SOC codes (O*NET has sub-codes like 11-1011.00, 11-1011.03)
    scores = df.groupby("soc_code").agg({
        "dv_rating_alpha": "mean",
        "dv_rating_beta": "mean",
        "dv_rating_gamma": "mean",
        "human_rating_alpha": "mean",
        "human_rating_beta": "mean",
        "human_rating_gamma": "mean",
    }).reset_index()
    return scores


def load_soc_noc2016() -> pd.DataFrame:
    """Load SOC 2018 → NOC 2016 correspondence table."""
    df = pd.read_csv(DATA_DIR / "soc2018_noc2016.csv", encoding="latin-1")
    df = df.rename(columns={
        "SOC 2018 (US) Code": "soc_code",
        "NOC 2016  Version 1.3 Code": "noc2016_code",
    })
    # Normalize codes to strings
    df["soc_code"] = df["soc_code"].astype(str).str.strip()
    df["noc2016_code"] = df["noc2016_code"].astype(str).str.strip()
    return df[["soc_code", "noc2016_code"]].drop_duplicates()


def load_noc2016_2021() -> pd.DataFrame:
    """Load NOC 2016 → NOC 2021 correspondence table."""
    df = pd.read_csv(DATA_DIR / "noc2016_noc2021.csv", encoding="utf-8-sig")
    df = df.rename(columns={
        "NOC 2016 V1.3 Code": "noc2016_code",
        "NOC 2021 V1.0 Code": "noc2021_code",
    })
    df["noc2016_code"] = df["noc2016_code"].astype(str).str.strip()
    df["noc2021_code"] = df["noc2021_code"].astype(str).str.strip()
    return df[["noc2016_code", "noc2021_code"]].drop_duplicates()


def main() -> None:
    print("Loading Eloundou scores...")
    eloundou = load_eloundou()
    print(f"  {len(eloundou)} unique SOC codes with scores")

    print("Loading SOC 2018 → NOC 2016 crosswalk...")
    soc_noc16 = load_soc_noc2016()
    print(f"  {len(soc_noc16)} mappings")

    print("Loading NOC 2016 → NOC 2021 crosswalk...")
    noc16_21 = load_noc2016_2021()
    print(f"  {len(noc16_21)} mappings")

    # Step 1: Join Eloundou scores to NOC 2016 via SOC
    merged = soc_noc16.merge(eloundou, on="soc_code", how="inner")
    print(f"\n  SOC→NOC2016 matched: {len(merged)} rows ({merged['noc2016_code'].nunique()} unique NOC2016 codes)")

    # Step 2: Chain to NOC 2021
    merged = merged.merge(noc16_21, on="noc2016_code", how="inner")
    print(f"  →NOC2021 matched: {len(merged)} rows ({merged['noc2021_code'].nunique()} unique NOC2021 codes)")

    # Step 3: Average scores per NOC 2021 code (many SOC codes may map to one NOC)
    score_cols = [c for c in merged.columns if "rating" in c]
    result = merged.groupby("noc2021_code")[score_cols].mean().reset_index()

    # Zero-pad NOC 2021 codes to 5 digits
    result["noc_code"] = result["noc2021_code"].str.zfill(5)

    # Compute combined alpha/beta/gamma (average of human + GPT-4 ratings)
    result["alpha"] = ((result["dv_rating_alpha"] + result["human_rating_alpha"]) / 2).round(4)
    result["beta"] = ((result["dv_rating_beta"] + result["human_rating_beta"]) / 2).round(4)
    result["gamma"] = ((result["dv_rating_gamma"] + result["human_rating_gamma"]) / 2).round(4)

    # Keep individual human and AI ratings for disagreement analysis
    result["human_alpha"] = result["human_rating_alpha"].round(4)
    result["human_beta"] = result["human_rating_beta"].round(4)
    result["human_gamma"] = result["human_rating_gamma"].round(4)
    result["ai_alpha"] = result["dv_rating_alpha"].round(4)
    result["ai_beta"] = result["dv_rating_beta"].round(4)
    result["ai_gamma"] = result["dv_rating_gamma"].round(4)

    # Max disagreement across all three tiers
    result["disagreement"] = result.apply(lambda r: max(
        abs(r["human_alpha"] - r["ai_alpha"]),
        abs(r["human_beta"] - r["ai_beta"]),
        abs(r["human_gamma"] - r["ai_gamma"]),
    ), axis=1).round(4)

    output = result[["noc_code", "alpha", "beta", "gamma",
                      "human_alpha", "human_beta", "human_gamma",
                      "ai_alpha", "ai_beta", "ai_gamma",
                      "disagreement"]].sort_values("noc_code")

    out_path = DATA_DIR / "eloundou_noc2021.csv"
    output.to_csv(out_path, index=False)
    print(f"\nSaved {len(output)} NOC 2021 codes to {out_path}")

    # Coverage check
    all_noc = pd.read_csv(DATA_DIR / "noc_structure.csv")
    all_unit_groups = all_noc[all_noc["Level"] == 5]["Code - NOC 2021 V1.0"].astype(str).str.zfill(5)
    matched = set(output["noc_code"]) & set(all_unit_groups)
    missing = set(all_unit_groups) - set(output["noc_code"])
    print(f"\nCoverage: {len(matched)}/{len(all_unit_groups)} unit groups ({100*len(matched)/len(all_unit_groups):.1f}%)")
    if missing:
        print(f"Missing {len(missing)} NOC codes (will use median scores as fallback)")

    # Score distribution
    print(f"\nScore distribution:")
    print(f"  Alpha (LLM alone):     mean={output['alpha'].mean():.3f}, median={output['alpha'].median():.3f}")
    print(f"  Beta  (LLM + tools):   mean={output['beta'].mean():.3f}, median={output['beta'].median():.3f}")
    print(f"  Gamma (LLM + all):     mean={output['gamma'].mean():.3f}, median={output['gamma'].median():.3f}")

    # Show some examples
    print(f"\nSample scores:")
    examples = {"21233": "Web designers", "21232": "Software developers",
                "14100": "General office workers", "72010": "Machining contractors",
                "31102": "Family physicians", "41200": "University professors"}
    for code, name in examples.items():
        row = output[output["noc_code"] == code]
        if len(row):
            r = row.iloc[0]
            print(f"  {code} {name}: α={r['alpha']:.3f} β={r['beta']:.3f} γ={r['gamma']:.3f}")
        else:
            print(f"  {code} {name}: NO MATCH")


if __name__ == "__main__":
    main()
