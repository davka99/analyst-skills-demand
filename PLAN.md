# PLAN – What Swedish employers ask of data analysts (job ads 2016–2025)

## Business question

A Swedish education provider planning a data-analyst programme (yrkeshögskola,
university contract education, or an employer's internal upskilling) has to decide
which tools and methods the curriculum should prioritise. Programmes approved by
Myndigheten för yrkeshögskolan must also document labour-market demand.

**Which skills do employers in Sweden ask for in data-analyst job ads, how has that
changed from 2016 to 2025, and does Stockholm differ from the rest of the country?**

Secondary questions:
- How has the number of data-analyst ads developed, relative to all ads on Platsbanken?
- Which skills appear together (skill bundles), and how often are AI/LLM skills mentioned?

Decision supported: the ranking of skills for a curriculum, with uncertainty, and
which skills are clearly rising or falling (not just noise).

## Data source and how it is fetched

| Source | What | Access |
|---|---|---|
| [JobTech / Arbetsförmedlingen – Historical job ads](https://jobtechdev.se/en/components/historical-ads) | All ads published on Platsbanken, one file per year (`https://data.arbetsformedlingen.se/annonser/historiska/`), raw `YYYY.zip` and enriched files in `berikade/` | Open download, no key |
| JobTech taxonomy labels inside each ad | Occupation, occupation group, region and municipality | Part of each ad record |

Study window: ads published 2016-01-01 to 2025-12-31 (complete years only).

The yearly files are large (hundreds of MB to a few GB). They are streamed in GitHub
Actions and filtered there: only the analyst-ad extract (ids, metadata, text), yearly
denominators for all ads and a fetch manifest are committed. The sandbox that builds
this project cannot reach the download host, so the pipeline runs in Actions
(`.github/workflows/analyst-skills-demand-pipeline.yml` in the workspace repo,
triggered by editing `pipeline_request.txt`; the standalone copy in
`.github/workflows/pipeline.yml` uses `workflow_dispatch`).

## Population (pre-registered, see `docs/brief.md` and D2)

Primary population: ads whose **headline** is classified as a data/BI analyst role by
`src/adskills/titles.py` (tested rules, frozen before any skill shares are computed).
Headline-based, because occupation coding changes over time and is set by the
employer; a taxonomy-based population is a robustness check (M7).

## Methods

- Data quality: record counts vs published totals, duplicates and re-postings
  (same employer + normalised headline + text hash), missing or very short
  descriptions, language (Swedish/English), recruitment agencies, taxonomy labels of
  the population.
- Skill extraction: transparent regex dictionary (`src/adskills/skills.py`), validated
  against a hand-annotated stratified sample: precision and recall per skill with
  Wilson intervals. Dictionary frozen before trend analysis.
- Prevalence: share of ads mentioning each skill per year, with **employer-cluster
  bootstrap** intervals (many ads come from the same employer).
- Trends: logistic regression of mention on year (and Stockholm vs rest) with
  employer-clustered standard errors; Benjamini–Hochberg across skills.
- Volume: analyst ads per 10,000 Platsbanken ads per year and by region.
- Skill bundles: co-occurrence (lift, phi). An exploratory topic model was tried and
  removed (D15, D16).
- Robustness: taxonomy-defined population, de-duplication variants, excluding
  recruitment agencies, Swedish vs English ads.

## Milestones (one per run)

- [x] M1. Scaffold: plan, brief, README skeleton, decisions log, pinned requirements,
      title classifier and skill dictionary v0 with tests, streaming reader for the
      yearly files, CI and pipeline workflows; source probe in Actions.
- [x] M2. Verify probe (file list, format, field names, sizes); full fetch + filter
      of 2016–2025 in Actions; extract, yearly denominators and manifest committed.
- [x] M3. Data-quality report (`docs/data_quality.md`) and clean analysis dataset
      with tested de-duplication rules; reconcile yearly ad counts with a published figure.
- [x] M4. Skill-extraction validation: annotation guide, stratified sample,
      precision/recall per skill with Wilson CIs; fix dictionary, then freeze it (D-log).
- [x] M5. Prevalence and trends: yearly shares with cluster-bootstrap CIs, logistic
      trend models with clustered SEs, BH correction; Stockholm vs rest.
- [x] M6. Volume and bundles: analyst ads per 10,000 ads by year and region,
      co-occurrence, exploratory NMF topics; AI/LLM mentions.
- [x] M7. Robustness checks (taxonomy population, de-dup variants, agencies, language)
      and segment check for Simpson's paradox (Stockholm vs rest by year).
- [x] M8. Final README with real results and uncertainty, figures, README-number
      check test, QA rerun from the committed extract, skeptic's three objections.

Max 15 build runs. Used: 9 (run 9: publishing without ad text, D16).

## Definition of Done

- [x] All data fetched by a script from the public source; manifest and extract committed
- [x] `docs/data_quality.md` written; no silent cleaning; yearly counts reconciled
- [x] Population and skill dictionary frozen and logged before trend results were seen
- [x] Skill extraction validated (precision/recall with CIs per skill)
- [x] Every share reported with an interval that accounts for employer clustering
- [x] Trend claims corrected for multiple comparisons
- [x] Stockholm vs rest checked per year (no aggregate-only conclusion)
- [x] Robustness checks done and reported, including where results change
- [x] `docs/decisions.md` covers every choice that affects results
- [x] README follows the portfolio standard; key numbers checked by a test
- [x] All tests pass locally and in GitHub Actions; QA rerun reproduces the results
