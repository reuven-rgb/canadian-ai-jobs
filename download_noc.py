"""Download all data sources: NOC structure, wages, COPS projections, Eloundou scores, crosswalks."""

import sys
from pathlib import Path

import httpx
import pandas as pd

DATA_DIR = Path("data")

SOURCES = {
    # NOC 2021 structure and occupation descriptions
    "noc_structure.csv": "https://www.statcan.gc.ca/en/subjects/standard/noc/2021/indexV1/noc-2021-v1.0-classification-structure.csv",
    "noc_elements.csv": "https://www.statcan.gc.ca/en/subjects/standard/noc/2021/indexV1/noc-2021-v1.0-elements.csv",
    # Wages
    "wages_2025.csv": "https://open.canada.ca/data/dataset/adad580f-76b0-4502-bd05-20c125de9116/resource/9da94d63-b178-4a64-aeb3-b6a3bd721ad2/download/2a71-das-wage2025opendata-esdc-all-19nov2025-vf.csv",
    # COPS 2024-2033 projections
    "cops_projected_conditions.csv": "https://open.canada.ca/data/dataset/e80851b8-de68-43bd-a85c-c72e1b3a3890/resource/446fe474-96e7-47cd-a3f9-3bb391b2df60/download/flmc_cfmt_2024_2033_noc2021.csv",
    "cops_employment_growth.csv": "https://open.canada.ca/data/dataset/e80851b8-de68-43bd-a85c-c72e1b3a3890/resource/7f0bf3be-c9ed-466b-bac8-f192a2776e0f/download/employment_growth_croissance_emploi_2024_2033_noc2021.csv",
    # Eloundou et al. LLM exposure scores
    "eloundou_scores.csv": "https://raw.githubusercontent.com/openai/GPTs-are-GPTs/main/data/occ_level.csv",
    # SOC → NOC crosswalk tables
    "soc2018_noc2016.csv": "https://www.statcan.gc.ca/en/statistical-programs/document/noc2016v1_3-soc2018us-eng.csv",
    "noc2016_noc2021.csv": "https://www.statcan.gc.ca/en/statistical-programs/document/noc2016v1_3-noc2021v1_0-eng.csv",
}


def download(name: str, url: str) -> Path:
    dest = DATA_DIR / name
    if dest.exists():
        print(f"  {name}: already exists, skipping download")
        return dest

    print(f"  {name}: downloading...")
    resp = httpx.get(url, follow_redirects=True, timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"  {name}: saved ({len(resp.content):,} bytes)")
    return dest


def summarize(path: Path) -> None:
    print(f"\n{'='*60}")
    print(f"  {path.name}")
    print(f"{'='*60}")

    # Try different encodings
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(path, encoding=enc)
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    else:
        print("  Could not parse CSV with any encoding")
        return

    print(f"  Rows: {len(df):,}  |  Columns: {len(df.columns)}")
    print(f"  Columns: {list(df.columns)}")
    print(f"\n  First 5 rows:")
    print(df.head().to_string(index=False))
    print(f"\n  Dtypes:")
    print(df.dtypes.to_string())

    # Look for NOC code columns
    for col in df.columns:
        if "noc" in col.lower() or "code" in col.lower():
            unique = df[col].nunique()
            sample = df[col].dropna().head(5).tolist()
            print(f"\n  Column '{col}': {unique} unique values, samples: {sample}")


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    print("Downloading Canadian occupation data...\n")
    paths = {}
    for name, url in SOURCES.items():
        try:
            paths[name] = download(name, url)
        except httpx.HTTPError as e:
            print(f"  ERROR downloading {name}: {e}", file=sys.stderr)
            sys.exit(1)

    for path in paths.values():
        summarize(path)


if __name__ == "__main__":
    main()
