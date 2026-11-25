# Data quality

Generated from `data/raw/fetch_manifest.json`, `data/raw/api_yearly_totals.json`
and `reports/data_quality_summary.json` (stage `quality`). Nothing was removed
silently: every dropped row has a reason that is counted below.

## 1. What was read

| | |
|---|---|
| Files | 11 enriched files (`berikade/kompletta/<label>_beta1_jsonl.zip`): 2016–2025 plus the boundary file 2026-Q1 (D6, D8) |
| Records read | 7.52 million (one JSON object per line) |
| Granularity | One row = one ad on Platsbanken. An ad can cover several vacancies (`number_of_vacancies`) |
| Kept in the extract | 15,242 ads whose headline matched any title category (population and neighbours); text used only by `build`, not committed (D16) |
| Analytical-occupation candidates | 167,121 unclassified ads with an analytical/data occupation code (headline and code only), used for the coverage check in section 6; recreated by `fetch`, not committed |

## 2. Reconciliation of yearly totals

Unique ads per **publication year** from the files, compared with an independent count
from JobTech's historical search API (same source, different system, filtered on the
same dates):

| Year | Files | API | Difference |
|---|---|---|---|
| 2016 | 686,950 | 686,137 | +0.1 % |
| 2017 | 715,291 | 714,266 | +0.1 % |
| 2018 | 682,969 | 683,668 | −0.1 % |
| 2019 | 640,374 | 641,602 | −0.2 % |
| 2020 | 493,131 | 495,440 | −0.5 % |
| 2021 | 733,028 | 734,398 | −0.2 % |
| 2022 | 1,060,070 | 1,060,191 | −0.0 % |
| 2023 | 1,026,755 | 1,030,902 | −0.4 % |
| 2024 | 715,470 | 717,333 | −0.3 % |
| 2025 | 581,440 | 621,875 | **−6.5 %** |

2016–2024 agree within half a percent, so the files are complete for those years.
**2025 is 6.5 % short of the API.** Numerator and denominator of the volume index come
from the same files, so the index is consistent, but 2025 volume is marked as less certain.

**Where the gap sits (stage `reconcile_monthly`, `data/raw/api_monthly_totals.json`).**
Per publication month, files against the API:

| Month | Files vs API |
|---|---|
| 2024-01 – 2024-10 | −0.4 % to +0.2 % |
| 2024-11 / 2024-12 | −0.9 % / −3.5 % |
| 2025-01 / 02 / 03 | −11.1 % / −9.9 % / −9.2 % |
| 2025-04 | **−25.3 %** |
| 2025-05 / 06 | +0.1 % / −3.3 % |
| 2025-07 / 08 | −7.2 % / **+10.1 %** |
| 2025-09 – 2025-12 | −1.6 % to +1.7 % |

- The gap is concentrated in Dec 2024 – Apr 2025 and Jul 2025, and August has *more* ads
  in the files than in the API, so it is not a uniform loss.
- **Membership test:** one page of 100 API ads at a random offset was drawn for every day
  of Jan–May, Jul and Aug 2025 (21,049 ads) and looked up by id in the 2025 file. 98.7 %
  are there. The 276 that are not are all removed ads published in July–August (largest groups:
  administration and finance, health care, education), i.e. about 3 % of those months.
- In January–April, **none** of the 12,000 sampled API ads was missing, although these
  months have the largest shortfall. The API only pages through the first 2,000 ads per
  query, so on busy days (April averages 2,600 a day) the tail could not be sampled;
  publication dates and ids in the sample match the queried day, so a different date field
  or duplicate hits do not explain it.
- **Conclusion:** a small, identified part of the gap is removed July–August ads missing
  from the file. The larger spring shortfall is located but not explained; JobTech's
  dataset is "continuously updated", and the 2026-Q1 file adds only 2,600 ads from 2025.

## 3. Duplicates

| Check | Result |
|---|---|
| Duplicate ids inside the 2016 file | 31,096 (4.3 % of the file); none in later files |
| Ids present in an earlier file | 1,011 (2022), 722 (2023), 763 (2024), 453 (2025), 415 (2026-Q1) |
| Population ads in window | 4,240 |
| – same id in two files (dropped) | 2 |
| – reposts: same employer, headline and identical text in the same year (dropped, D9) | 597 (14.1 %) |
| **Population after de-duplication** | **3,641 ads** from 1,180 employers |

Yearly denominators count each id once (first occurrence).

## 4. Completeness and validity

| Field | Finding | Handling |
|---|---|---|
| Description | 18,837 ads in the 2020 file (3.8 %) have no text at all; other years < 0.3 %. In the population: 12 empty, 17 under 200 characters | Excluded from skill shares only (D12) |
| Publication date | 3 records in the 2020 file dated 2051 or 2099 | Outside the window, dropped |
| Region | Missing for 4.9 % of population ads (incl. ads abroad, e.g. Malta, Dubai). For 2016 the region was derived from the municipality code for 1,721 extract rows (D8) | Area = "Unknown"; excluded from the Stockholm comparison only |
| Occupation | Present for > 99.5 % of ads; one concept per ad | Not used to define the population (D2) |
| Language | `detected_language`: 50 % English, 50 % Swedish in the population | Robustness split in M7 |

## 5. Population: size, mix and concentration

| Year | Ads | per 10,000 Platsbanken ads | data analyst | analytics-type | BI analyst | English |
|---|---|---|---|---|---|---|
| 2016 | 216 | 3.1 | 36 | 166 | 14 | 26 % |
| 2017 | 217 | 3.0 | 61 | 145 | 11 | 26 % |
| 2018 | 274 | 4.0 | 104 | 147 | 23 | 38 % |
| 2019 | 325 | 5.1 | 146 | 163 | 16 | 44 % |
| 2020 | 249 | 5.0 | 137 | 101 | 11 | 54 % |
| 2021 | 513 | 7.0 | 275 | 211 | 27 | 56 % |
| 2022 | 578 | 5.5 | 335 | 203 | 40 | 61 % |
| 2023 | 487 | 4.7 | 310 | 152 | 25 | 59 % |
| 2024 | 415 | 5.8 | 270 | 116 | 29 | 54 % |
| 2025 | 367 | 6.3 | 253 | 94 | 20 | 47 % |

- **Small samples.** 216–578 ads a year, so a yearly share has a 95 % interval of
  roughly ±4–7 percentage points before clustering. Period pooling (D10) is needed
  for firm statements.
- **The title mix changes** from mostly marketing/web/commercial analysts in 2016 to
  mostly "data analyst" titles in 2025. Trends are therefore also reported within
  title category (D11).
- **Employer concentration:** the ten largest employers post 20 % of the ads
  (H&M 162, Academic Work 183 under two names, Volvo Business Services 99). Shares
  get employer-cluster intervals (D10).
- **Recruitment and staffing firms** post 17.8 % of the ads, falling from 36 % in
  2016 to 11–16 % in 2023–2025. Their effect is checked in M7.
- **Stockholm** (Stockholms län) has 63 % of the ads with a known region.

## 6. Does the headline rule miss analyst ads?

The JobTech taxonomy has no data-analyst occupation before 2023. The population is
spread over many codes: Marknadsanalytiker (812), Systemanalytiker (462),
Dataingenjör (210), Verksamhetsanalytiker (162) and others. This supports defining
the population by headline (D2).

From 2023 a "Dataanalytiker" code exists: 36 population ads carry it, and 45 ads
with that code were *not* caught by the headline rule. Reading those 45 headlines,
about 7 are plausibly data-analyst roles ("Data Analytics Lead, Consumer Pricing",
"Analytiker till Datadriven utveckling på Swedavia", "Senior Specialist, Commercial
Analytics"); the rest are other jobs (master data, KYC, fraud, quality analysts in
Riga, business analysts). Rough recall within that code: 36 / 43 ≈ 84 %. This is a
small, recent subset, so it is an indication, not an estimate for all years.

## 7. Open points carried forward

- 2025 total 6.5 % below the API (section 2).
- Composition change in titles (D11) and in agencies (M7).
