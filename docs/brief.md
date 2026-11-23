# Brief

Written before any ad data was downloaded.

## Decision and decision-maker

An education provider (yrkeshögskola, university contract education or an
employer's internal academy) designs a data-analyst programme for the Stockholm
labour market. It must decide which tools and methods get teaching time, and it must
document labour-market demand in its application. The analysis gives a ranked list
of skills with uncertainty and shows which skills are clearly rising or falling.

## Metric

**Skill share** for skill *s* in year *t* and region *r*:

- Numerator: de-duplicated ads in the population, published in year *t* (by
  `publication_date`, Swedish local date), located in *r*, whose headline or
  description mentions *s* according to the frozen dictionary.
- Denominator: all de-duplicated ads in the population for *t* and *r*.
- Unit: an ad (not a vacancy: one ad can cover several positions; reported separately).
- Population: Platsbanken ads 2016–2025 whose headline is classified as a data/BI
  analyst role by `titles.classify_headline` (categories `data_analyst`,
  `bi_analyst`, `analytics_analyst`).
- Region: Stockholm = Stockholms län (workplace region). Ads without a region are
  reported as a separate group, not dropped.

**Volume index**: population ads per 10,000 Platsbanken ads in the same year.

## What counts as done

- Skill shares per year with intervals that account for clustering by employer.
- Trend estimate per skill (odds ratio per year) with BH-adjusted p-values.
- Stockholm vs rest of Sweden, checked year by year.
- Extraction precision and recall per reported skill, from a hand-annotated sample.

## Results that would NOT answer the question

- Shares computed on all IT ads or on "analyst" in any sense (financial analyst,
  system analyst): different population.
- Word counts without a validated mapping from words to skills.
- Shares without uncertainty, or trends driven by one large employer re-posting.

## Must not change silently

Population rules (title classifier), study window, de-duplication rule, region
definition, the skill dictionary after it is frozen (M4). Any later change is logged
in `docs/decisions.md` as a post-result change.

## Sub-questions, in order

1. Do the yearly files exist for 2016–2025, in what format, with which fields? (probe)
2. How many analyst ads per year, and how clean are they? (M2–M3)
3. How accurate is the skill extraction? (M4)
4. Shares and trends; Stockholm vs rest (M5)
5. Volume, bundles, AI mentions (M6)
6. Robustness (M7)
