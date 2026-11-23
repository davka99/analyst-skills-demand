# QA

## 1. Reproducibility

All offline stages (`quality validate prevalence bundles robustness`) were re-run from
the committed extract in one GitHub Actions job (Python 3.12, pinned requirements,
seed `20261120`), run 44699365193 at commit `13871a6`. Result: every result file in
`reports/` (`data_quality_summary.json`, `validation.json`, `prevalence.json`,
`bundles.json`, `robustness.json`) was **byte-identical** to the committed version.
`data/processed/analyst_ads.jsonl.gz` differed only in the gzip header timestamp; the
decompressed content has the same SHA-256 (`fbe3b7e7…`). Gzip files are now written
with a fixed header time so future reruns are byte-identical too. The only other
changed file was the hero figure, whose generated title was updated in that commit.
184 tests passed in the same job.

After ad text was removed (D16), the offline stages were re-run from the features
file in Actions: every count, share, difference, odds ratio, p-value, validation metric,
volume and co-occurrence figure was identical, and the annotation samples were re-drawn
identically. Bootstrap interval *endpoints* moved by at most 1 percentage point (e.g.
SQL 30–40 % → 30–41 %): employer keys are now hashed, which changes the order of
employers and therefore which employers each seeded bootstrap draw picks. That is
Monte Carlo variation of the interval, not a change in the data; the README uses the
new values. Ties in the top-employer list are now broken by name. A second rerun on
the same input (run 45104965087) reproduced every result; the only differences were
in the 12th–13th significant digit of a few GLM confidence limits and p-values
(floating-point noise in the model fit), which no reported number shows.

## 2. Consistency checks

- `scripts/check_readme.py` recomputes 41 numbers quoted in the README from
  `reports/*.json` and fails the test suite if any differ (`tests/test_readme_numbers.py`).
- Figure titles are generated from the results, not typed by hand.
- Yearly totals: files vs JobTech search API within ±0.5 % for 2016–2024 (2025: −6.5 %,
  unexplained, see `docs/data_quality.md`).
- Skill extraction vs JobTech's own skill tags: agreement 94–99 % per tool on the same ads.

## 3. The three strongest objections, and answers

**1. "You measured job-ad wording, not skill demand."**
True in part, and the project is built around it. The metric is defined as *share of
ads that mention a skill* (brief), never as "required". Two results show why the
distinction matters and how it was handled: "English required" fell sharply, but only
in English-language ads, so the README reports it as a change in how ads are written
(finding 5). Generic mentions ("AI" in a company description) are labelled "any
mention". What remains — Excel and SAS down, Python, cloud and visualisation up —
holds in eight variants, including Swedish-only and English-only ads, so it is not a
wording artefact of one ad style.

**2. "The trends are just a change in which jobs are called data analyst."**
Partly, and that is reported as a finding rather than hidden. Because the title mix
changed (17 % → 69 % "data analyst"), every trend was pre-registered to be shown
pooled, adjusted for title, and within data-analyst titles (D11, before results).
SQL's pooled rise disappears within titles and is described as a title-mix effect;
Python, cloud platforms, visualisation, Excel and SAS change within titles too.

**3. "Your validation is circular — an AI wrote the rules and an AI checked them."**
The annotators were separate sub-agents that saw only the ad text and a written
guide, never the rules or their output. Rules were fixed on a development sample and
committed (with a hash) before the test sample was compared. Disagreements were
adjudicated with a written reason per case, all files are committed for audit, and
the two bug fixes made after testing are logged with before/after numbers (D14). An
independent extraction that ships with the data (JobTech's tags) agrees on 94–99 % of
ads and shows the same trends. Human expert annotation would still be stronger; the
README says so.

## 4. Other known weaknesses

- Platsbanken coverage of tech jobs may have changed over the decade.
- Annual samples are small; single-year wiggles (e.g. Power BI in 2019) are not
  interpreted.
- An exploratory topic model mostly recovered language and employer templates (D15)
  and was removed when ad text was taken out of the repo (D16).
