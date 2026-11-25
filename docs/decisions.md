# Decisions log

Every choice that affects results: what, why, alternatives, impact.
Changes made after seeing results are marked **post-result** and kept separate from
diagnostic fixes.

## D1 – Data source: JobTech historical ads (M1)

- **What:** Arbetsförmedlingen/JobTech historical Platsbanken ads, yearly files.
- **Why:** The only open, complete, multi-year source of Swedish job ads with full
  text. No API key, so a scheduled pipeline can fetch it.
- **Alternatives:** JobSearch API (current ads only, offset limit 2,000); LinkedIn or
  scraping (terms of use, not reproducible); SCB vacancy statistics (no ad text).
- **Impact:** Platsbanken is not every ad in Sweden. Some employers post only on
  their own site or LinkedIn, and the coverage of tech roles may be lower than for
  other occupations. Results describe Platsbanken ads, and the README says so.

## D2 – Population defined by headline, not occupation code (M1)

- **What:** An ad is in the population if its headline is classified as a data
  analyst, BI analyst or analytics/insight/reporting analyst
  (`titles.classify_headline`). Data scientist, data engineer, business analyst
  (verksamhetsanalytiker), system analyst, financial/credit analyst and generic
  "analytiker" headlines are excluded.
- **Why:** Occupation codes are chosen by the employer from a taxonomy that changed
  over the period (new occupation names added). A headline rule is the same for all
  years and can be audited. Excluding generic "analytiker" keeps policy analysts and
  financial analysts out of a data-analyst skill profile.
- **Alternatives:** taxonomy occupation names (robustness check in M7); a broader
  rule that includes generic analyst titles (reported as a sensitivity).
- **Impact:** Misses data-analyst roles with unusual headlines; recall of the rule is
  estimated in M3 by reading a sample of excluded ads with analyst occupation codes.

## D3 – Window 2016–2025, complete years only (M1)

- **What:** Ads published 2016-01-01 to 2025-12-31.
- **Why:** Ten complete years; avoids the SSYK96/SSYK2012 taxonomy transition around
  2014 that JobTech warns about; 2026 is incomplete at the time of analysis.
- **Impact:** No pre-2016 baseline.

## D4 – Skill extraction by a transparent dictionary (M1)

- **What:** Case-insensitive regular expressions per skill, written for Swedish and
  English ads (`src/adskills/skills.py`), validated in M4 against hand annotation.
- **Why:** Every match can be explained in an interview and audited; precision and
  recall can be measured per skill. JobTech's own enrichment is a black box and its
  method may change between yearly files.
- **Alternatives:** JobTech enriched `keywords` (compared as a check if present in
  the files), embeddings or an LLM classifier (harder to reproduce and audit).
- **Impact:** Recall depends on the dictionary; measured and reported.

## D5 – Title exclusions found in the probe (M1, before any skill results)

- **What:** Headlines with "Online Data Analyst" (crowd-work search-rating gigs) and
  "Master Data Analyst" (master-data management in ERP systems) are classified as
  `online_rater` / `master_data` and kept out of the population.
- **Why:** Both appeared in the 2024 probe sample and are different jobs. Found by
  reading headlines, not by looking at skill shares, so this is a diagnostic fix.
- **Impact:** Small (a handful of ads per year); counts are kept in the extract so
  the effect can be reported.

## D6 – File layout and the boundary file (M1 probe)

- **What:** Files are `YYYY.jsonl.zip` (one JSON object per line, ~4 GB unzipped for
  2024). The 2024 file contains ads published from mid-2023, so files appear to be
  grouped by when an ad ended, not by publication date. The analysis assigns ads to
  years by `publication_date`, scans `2026-Q1.jsonl.zip` as a boundary file to catch
  ads published in late 2025, and tracks ids across files to find ads that appear
  in two files.
- **Why:** Using the file year would mix publication years and could double count.
- **Alternatives:** the `*_municipality_patched` files for 2018–2019 (a JobTech fix to
  municipality fields); the plain files are used and region completeness is checked
  in M3. If 2018–2019 regions look broken, the patched files are compared.
- **Impact:** Ads published in December 2015 that sit in the 2016 file are dropped by
  the window; ads published in 2025 that sit in later 2026 files (after Q1) would be
  missed, which M3 checks against the monthly profile.

## D7 – Taxonomy fields are lists; first concept used (M1 probe)

- **What:** `occupation`, `occupation_group` and `occupation_field` are lists of
  concepts. The first concept is used.
- **Why:** The probe showed a list with one element in the sampled records; M3
  reports how often there is more than one.

## D8 – Use JobTech's enriched files for every year (M2, schema stage)

- **What:** All years are read from `berikade/kompletta/<year>_beta1_jsonl.zip`
  instead of the raw `YYYY.jsonl.zip`.
- **Why:** The schema stage (`data/raw/_probe/schema/`) showed that the raw files
  change over time: 2016 has no ad id, 2016–2019 have no occupation labels and no
  region names, 2018–2019 have no municipality code either. The enriched files have
  an id for every ad (same hash format in all years), occupation labels, a detected
  language and JobTech's own skill extraction. Where the region name is missing
  but the municipality code exists (2016), the county is derived from the first two
  digits of the code (`jobtech.COUNTY_BY_CODE`, tested).
- **Alternatives:** raw files plus the `*_municipality_patched` files for 2018–2019
  (regions fixed, but still no language and a different id scheme in 2016).
- **Impact:** One consistent schema. The text and headline are the same fields, so
  the population rule and the skill dictionary are unaffected. Ad counts per year
  are compared with the raw files in M3 (2024 raw: 717,094 ads).
- **Known gap:** in the first 20,000 records of 2020 only 77 % have a description
  and 71 % a region, in both raw and enriched files. Checked over the full year in M3.

## D9 – De-duplication and recruitment agencies (M2, before the extract was read)

- **What:** (1) the same ad id in two files is kept once (first file); (2) a
  *repost* is the same employer (org. number, else normalised name), the same
  normalised headline and an identical normalised description in the same
  publication year; only the earliest is kept. Staffing/recruitment firms are
  flagged by a name list (`quality.AGENCY`), not dropped.
- **Why:** Re-posted ads would let one employer's template count several times.
  Requiring identical text keeps genuinely new positions with the same title.
  Agencies post on behalf of unnamed clients; dropping them would remove real
  demand, so their effect is a robustness check (M7).
- **Alternatives:** a 60-day window instead of the calendar year; near-duplicate
  text (MinHash). The window variant is a sensitivity in M7.

## D10 – Analysis plan for M5, written before any skill share was computed on the full data

- **Unit and population:** de-duplicated population ads 2016–2025 (D2, D9), skills
  from headline + description with the dictionary frozen in M4.
- **Headline ranking ("what to teach now"):** shares in the latest three years
  2023–2025, with 95 % employer-cluster bootstrap intervals (2,000 draws, seed in
  `config.SEED`).
- **Change:** late (2023–2025) minus early (2016–2018) share, with an interval from
  resampling employers once for both periods. Trend: logistic regression of
  mention on year with employer-clustered SEs; Benjamini–Hochberg across all
  reported keys (q = 0.05).
- **"Clearly rising/falling"** requires both BH-adjusted p < 0.05 for the trend and
  a late–early difference of at least 5 percentage points whose interval excludes
  0. Anything else is "no clear change", whatever the point estimate.
- **Stockholm vs rest:** late-period difference (cluster bootstrap) and a logistic
  model with year fixed effects + area, clustered by employer; per-year shares by
  area are shown so an aggregate gap can't hide a reversal (Simpson check).
  Ads without region are excluded from this comparison only and counted.
- **Measurement quality gate:** a skill whose test-sample precision is below 0.80
  is not ranked; it is reported in a separate table with its precision. Recall is
  reported next to every share.
- **Derived groups:** any cloud (Azure/AWS/GCP/Snowflake/Databricks/"cloud"), any BI
  tool (Power BI/Tableau/Qlik/Looker), Python or R.

## D11 – Title mix changes over time; trends also within titles (M3, before skill results)

- **What:** M3 showed that the population's title mix changes: in 2016, 77 % of
  population ads were analytics-type titles (marketing/web/commercial analyst) and
  17 % "data analyst"; in 2025 the split is 27 % / 69 %. Every trend in M5 is
  therefore reported (a) pooled, (b) with title category as a covariate
  (`C(category)`), and (c) for `data_analyst` titles alone. If they disagree, all
  three are shown and the README says which one answers which question.
- **Why:** A pooled rise in, say, Python could come only from more ads being titled
  "data analyst". That is a real market change, but a different finding from "the
  same role now asks for more Python". This is the Simpson's-paradox check for
  composition, decided before any skill share was computed on the full data.

## D12 – Ads with almost no text are left out of skill shares (M3)

- **What:** Population ads with a description shorter than 200 characters (17 of
  3,641) are excluded from skill shares and counted; they stay in volume counts.
- **Why:** A missing description cannot mention a skill, so it would bias every share
  downwards. The 200-character cut-off was chosen by reading those ads (headline
  only, or one line), before any skill results.

## D13 – Dictionary v1 frozen after the development sample (M4)

- **What:** Compared with independent annotation of the development sample (100
  ads, 10 per year), v0 had perfect precision on every tool but low recall on the
  softer keys: reporting 33 %, Swedish requirement 21 %, English requirement 33 %,
  communication 62 %, degree 65 %. Fixes, all from reading the missed phrases:
  - reporting: Swedish nouns and compounds ("bygga rapporter", "veckorapporter") and
    English "reports"; a reporting *line* ("reports to the CTO", "rapporterar till")
    is excluded.
  - degree: "examen", "högskoleutbildning", "universitetsutbildning", MSc, PhD,
    "degree" (not "degree of").
  - language requirements: "svenska och engelska", skill words near the language
    ("flytande", "obehindrat", "fluency in"), and "not a requirement" excluded.
  - communication: "kommunicera/communicate", "presentera insikter/resultat".
  - R in chained lists ("SQL, Python, or R"), "PBI" for Power BI, "Data Vault",
    "förutse/predict", "AB testing", "data … visuell".
  - statistics now also counts compounds ("webbstatistik"). Annotators disagreed on
    whether "statistik" meaning *figures* counts; a regex cannot separate the two
    senses, so the key is defined and labelled as **"Statistics (any mention)"**.
- **Guide clarifications** (`docs/annotation_guide.md`, section "v1 clarifications"):
  statistics = any mention; communication includes presenting/explaining results;
  a language asked for as a merit counts. They are applied when adjudicating
  disagreements on the test sample.
- **Freeze:** `skills.py` is frozen at this commit (sha256 recorded in
  `reports/validation_test.json`). The test sample (150 ads) is compared with the
  dictionary only after this commit.
- **Honesty note:** dev-sample metrics after the fixes are optimistic by
  construction (the fixes were made on those ads) and are not reported as accuracy.

## D14 – Test-sample validation and two bug fixes (v1.1) – post-result, logged

- **Test sample:** 150 ads (15 per year), annotated independently in three batches.
  14 of 81 disagreements were adjudicated against the v1 clarifications
  (`data/annotation/adjudication_test.csv`, each with a reason): 10 communication
  and 4 statistics labels; all other disagreements keep the annotator's label.
- **Frozen v1 result** (`reports/validation_v1_frozen.json`): precision ≥ 0.92 for
  every key with at least one positive, except **cloud_any (0.60, 3 of 5)**:
  "Adobe Marketing Cloud" is a product name. Recall ≥ 0.88 for all tools except
  Azure 0.75 and AWS 0.80 (misspelling "Azur", service name "Redshift");
  degree 0.83, experimentation 0.77.
- **Bug fixes after seeing the test results (v1.1):** two places where the code did
  not do what D13 says it does:
  1. "reporting to the head …" was counted, because the regex could stop at
     "report" and skip the "to" look-ahead. Fixed by requiring a complete word
     (and "rapporterar du till" word order).
  2. "svenska och engelska" was added to English but not to Swedish requirement.
  No new vocabulary was added. Effect on the test sample: reporting FP 5 → 3,
  Swedish requirement recall 0.85 → 0.94. Because these are measured on the same
  sample that revealed them, v1.1 numbers for these two keys are slightly
  optimistic; the frozen v1 numbers are kept next to them.
- **Known misses not fixed** (vocabulary, would need a new validation sample):
  misspellings ("Tableu", "Azur"), "prediktion", "datalagret", "maskinlärande",
  "civilekonom/civilingenjör", "higher education", English "communicative",
  "excel" as a verb ("help you excel", 1 false positive). Shares of these keys are
  therefore slightly under-counted (degree most, recall 0.83).
- **Gate (D10):** cloud_any fails the 0.80 precision gate and is not ranked; the
  derived `any_cloud` group is reported both with and without it.
  Snowflake, genAI and YH had no positives in the test sample, so their precision
  and recall are unmeasured; they are reported with that caveat.

## D15 – Exploratory topic model: preprocessing changed after a first look (M6, exploratory)

- **What:** the first NMF run (no stop words) produced topics made of function words.
  Swedish + English stop words and a higher document-frequency floor were added,
  k = 6 kept as fixed in advance.
- **Result:** topics still mostly separate language (Swedish vs English ads) and
  large employers' templates (Academic Work boilerplate, Volvo, H&M). The topic
  model is therefore reported as exploratory only and used for no conclusion.
  This is logged because it was changed after seeing output.

## D16 – Publish without ad text (after M8, owner's decision)

- **What:** No ad text is committed. A new stage `build` reads the fetched extract
  once and writes `data/processed/ads_features.csv.gz`: one row per ad with id,
  dates, title category, region, language, employer name, hashed employer key,
  hashed headline/text keys (for de-duplication) and a 0/1 flag per skill. Every
  later stage reads only that file. The extract (`data/raw/extract/`), the
  analysis file with text and the annotation batches with text are git-ignored and
  recreated by `fetch`, `build` and `annotate_prep`. Annotations are kept as ad id
  + labels (`data/annotation/sample_ids.csv`, `ann_*.jsonl`).
- **Why:** The owner asked for it before publishing. The ads are employers' texts
  and can contain contact persons' names; the licence for redistributing full text
  was not confirmed. The id lets anyone fetch an ad from JobTech.
- **Check:** after the change, `data_quality_summary.json`, every number in
  `validation.json` and the volume and co-occurrence results were identical to the
  version computed from text; the annotation samples are re-drawn identically from
  the features file. The exploratory topic model needed text and gave no usable
  result (D15), so it was removed rather than kept as a text-only stage.
- **Impact:** None on results. Re-running from raw data takes `fetch` + `build`.

## R1 – Results of M5–M7 (summary; numbers in reports/*.json)

- Stated in the README; robust findings are those that keep sign and stay clear of
  0 in all eight variants of `reports/robustness.json`.
- Two interpretations were changed by the robustness checks, both stated in the
  README: (1) SQL's pooled rise is a title-mix effect (flat within data/BI analyst
  titles); (2) the fall in "English required" happens only in English-language ads
  (−46 pp) and not in Swedish-language ads (−2 pp, ~40 % every year), so it reflects
  how English-language ads are written, not lower demand for English.

## D17 – 2025 shortfall investigated (after publication)

Stage `reconcile_monthly` compares files and API per month and tests whether sampled API ads
exist in the 2025 file (`docs/data_quality.md`, section 2). Result: the gap is concentrated
in Dec 2024 – Apr 2025 and July; 98.7 % of 21,049 sampled API ads are in the file, and the
1.3 % missing are removed July–August ads. The spring shortfall remains unexplained. No
analysis result changes: the volume index uses the files for numerator and denominator.

## D18 – Human check of the AI-assisted annotation (after publication)

The repository owner labels 40 random ads from the test sample blind for 15 main skills
(`docs/annotation_guide.md`, "Human check"); `human_check` reports agreement and Cohen's
kappa with the adjudicated reference and with the dictionary. The kit with ad texts is built
in GitHub Actions and kept as a 7-day artifact, so no ad text is committed (D16).
