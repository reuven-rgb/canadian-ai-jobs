# Canadian AI Exposure of the Job Market

## Project Overview

Build a Canadian version of [JoshKale/jobs](https://github.com/JoshKale/jobs) — an interactive treemap visualization showing AI exposure for every occupation in the Canadian economy, using National Occupational Classification (NOC) 2021 data.

**Live reference of the US version:** https://joshkale.github.io/jobs/

## Architecture

Python data pipeline + static HTML/JS site. Use `uv` for dependency management.

### Pipeline Steps

1. **Download NOC structure** (`download_noc.py`) — Get the NOC 2021 classification structure CSV from StatCan and the Job Bank wages CSV from Open Government Portal. No scraping needed for these.
   - NOC structure CSV: https://www.statcan.gc.ca/eng/statistical-programs/document/NOC-CNP-2021-Structure-V1-eng.csv
   - 2025 Wages CSV: https://open.canada.ca/data/dataset/adad580f-76b0-4502-bd05-20c125de9116/resource/9da94d63-b178-4a64-aeb3-b6a3bd721ad2/download/2a71-das-wage2025opendata-esdc-all-19nov2025-vf.csv

2. **Scrape Job Bank profiles** (`scrape.py`) — For each 5-digit NOC unit group (~516 occupations), scrape the Job Bank profile page. URLs follow the pattern: `https://www.jobbank.gc.ca/marketreport/summary-occupation/{id}/ca` where `{id}` is a Job Bank internal ID. Use Playwright (non-headless, Job Bank may block bots). Start by scraping the occupation search/listing page to discover all occupation URLs and their NOC codes.
   - Alternative: scrape `https://noc.esdc.gc.ca/` which has detailed descriptions per NOC code
   - Job Bank occupation explorer: https://www.jobbank.gc.ca/occupation_search-eng.do

3. **Parse to Markdown** (`parse.py`) — Convert scraped HTML to clean Markdown per occupation. Extract: job title, NOC code, duties, education/training requirements, skills, work environment description.

4. **Build occupations CSV** (`make_csv.py`) — Merge NOC hierarchy, wages (median hourly → annual salary), employment counts (from Census or LFS), TEER category, and outlook into `occupations.csv`.

5. **Score AI exposure** (`score.py`) — Send each occupation's Markdown description to an LLM with a scoring rubric. Score 0-10 with rationale. Use Claude API (claude-sonnet-4-20250514) or OpenRouter. Save to `scores.json`.
   - Use the same scoring rubric as the original project (see below)
   - Consider Canadian-specific factors (bilingual requirements, regulatory differences)

6. **Build site data** (`build_site_data.py`) — Merge CSV stats + AI scores into compact `site/data.json`.

7. **Build site** (`site/index.html`) — Interactive treemap. Area = employment count, color = AI exposure (green→red). Group by NOC broad occupational category.

## Data Sources

| Data | Source | Format | URL |
|------|--------|--------|-----|
| NOC 2021 structure (codes, titles, hierarchy) | StatCan | CSV | statcan.gc.ca/en/subjects/standard/noc/2021/indexV1 |
| Occupation descriptions & duties | Job Bank or NOC/ESDC | HTML (scrape) | jobbank.gc.ca or noc.esdc.gc.ca |
| Wages (min/median/max hourly) | ESDC Open Data | CSV | open.canada.ca Wages dataset |
| Employment counts by NOC | StatCan Census 2021 | CSV | Table 98-10-0412-01 |
| Outlook (3-year projections) | Job Bank | HTML (scrape) | jobbank.gc.ca/trend-analysis |
| TEER categories | StatCan | CSV (included in NOC structure) | Same as NOC structure |

## NOC 2021 Hierarchy

- 10 Broad Occupational Categories (1st digit): 0-9
- 6 TEER levels (2nd digit): 0-5
- 45 Major Groups (2 digits)
- 89 Sub-major Groups (3 digits)
- 162 Minor Groups (4 digits)
- ~516 Unit Groups (5 digits) ← this is our target granularity

## AI Exposure Scoring Rubric

Use the same rubric from the original project. Score each occupation 0-10:

| Score | Meaning | Examples |
|-------|---------|----------|
| 0-1 | Minimal | Roofers, janitors, construction labourers |
| 2-3 | Low | Electricians, plumbers, nurse aides, firefighters |
| 4-5 | Moderate | Registered nurses, retail workers, physicians |
| 6-7 | High | Teachers, managers, accountants, engineers |
| 8-9 | Very high | Software developers, paralegals, data analysts, editors |
| 10 | Maximum | Medical transcriptionists |

Key signal: Is the work product fundamentally digital? Can the job be done entirely from a home office on a computer? If yes, AI exposure is inherently high.

## Tech Stack

- Python 3.12+ with `uv`
- Playwright for scraping
- BeautifulSoup4 for HTML parsing
- Anthropic SDK or OpenRouter for LLM scoring
- D3.js or similar for treemap visualization
- Static HTML/CSS/JS site (no framework needed)

## Environment Variables

```
ANTHROPIC_API_KEY=...       # For Claude API scoring
# OR
OPENROUTER_API_KEY=...      # For OpenRouter scoring
```

## File Structure

```
canadian-ai-jobs/
├── CLAUDE.md               # This file
├── pyproject.toml
├── .python-version
├── .env                    # API keys (gitignored)
├── .gitignore
├── data/
│   ├── noc_structure.csv   # Downloaded NOC hierarchy
│   ├── wages_2025.csv      # Downloaded wages data
│   └── employment.csv      # Census employment counts
├── html/                   # Raw scraped HTML
├── pages/                  # Parsed Markdown per occupation
├── occupations.csv         # Merged structured data
├── occupations.json        # Master occupation list
├── scores.json             # AI exposure scores + rationales
├── download_noc.py
├── scrape.py
├── parse.py
├── make_csv.py
├── score.py
├── build_site_data.py
└── site/
    ├── index.html
    ├── data.json
    └── style.css
```

## Development Notes

- Start with downloading the freely available CSVs before attempting any scraping
- Job Bank scraping may require non-headless Playwright — test first
- The NOC ESDC site (noc.esdc.gc.ca) may be easier to scrape for descriptions than Job Bank
- Wages are hourly — convert to annual assuming 2,080 hours (40hr × 52wk)
- Census employment data may only be available at 4-digit minor group level — may need to distribute proportionally to 5-digit unit groups
- Score in batches with rate limiting to avoid API throttling
- Cache everything — scraping and scoring are expensive operations