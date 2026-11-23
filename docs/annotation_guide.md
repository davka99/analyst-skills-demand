# Annotation guide (skill-extraction validation, M4)

Purpose: an independent reference to measure the precision and recall of the regex
skill dictionary (`src/adskills/skills.py`). Annotators see the ad text and this
guide, **not** the regular expressions.

## Unit and question

For each ad (headline + description) and each skill below, answer:
**Does the ad refer to this skill, tool or requirement?** (1 = yes, 0 = no)

- A mention anywhere counts: duties, requirements, "meriterande" (merit), the team's
  tech stack, or the company description. The project measures what ads *mention*,
  not only hard requirements.
- Spelling, case, Swedish compounds and English/Swedish variants all count:
  "Excelkunskaper", "SQL-frågor", "maskininlärning".
- A word that only *looks* like the skill does not count: "excellent" is not Excel,
  "R&D" is not R, SAS as the airline is not the SAS software, a person called Kai is
  not AI.
- Generic statements count only when the guide says so (e.g. "programming" alone is
  none of the language skills).
- When unsure, choose 0 and write a short note.

## Skills

| Key | Count as 1 when the ad refers to … |
|---|---|
| excel | Microsoft Excel (spreadsheets in Excel, Excel modelling, "Excel-kunskaper") |
| sql | SQL or an SQL dialect/database by name (T-SQL, PL/SQL, MySQL, PostgreSQL, SQL Server) |
| python | Python (incl. pandas, PySpark mentioned as Python) |
| r | The R programming language (R, RStudio, R-programmering) |
| sas | SAS software (not the airline) |
| spss | IBM SPSS |
| stata | Stata |
| vba | VBA / Excel macros written in VBA |
| power_bi | Microsoft Power BI |
| dax | DAX (Power BI / Analysis Services formula language) |
| tableau | Tableau |
| qlik | Qlik, QlikView, Qlik Sense |
| looker | Looker, Looker Studio, Google Data Studio |
| azure | Microsoft Azure (any Azure service) |
| aws | Amazon Web Services (any AWS service) |
| gcp | Google Cloud Platform or BigQuery |
| snowflake | Snowflake |
| databricks | Databricks |
| dbt | dbt (data build tool) |
| spark | Apache Spark / PySpark |
| git | Git, GitHub, GitLab, version control with Git |
| cloud_any | The words cloud / molnet / molntjänster in a technical sense (regardless of vendor) |
| statistics | Statistics or statistical methods/knowledge, incl. a degree in statistics |
| machine_learning | Machine learning / maskininlärning / ML models |
| forecasting | Forecasting, prognoser, predictive modelling/analytics |
| experimentation | A/B tests, experiments in a product/marketing sense, experimentation |
| etl_dw | ETL/ELT, data warehouse/datalager, data modelling |
| visualization | Data visualisation, dashboards |
| reporting | Reporting (rapportering) as a task |
| ai_any | AI / artificial intelligence mentioned in any way |
| genai | Generative AI, LLMs, ChatGPT/GPT, Copilot, language models |
| degree | A university/college degree (högskole-/universitetsexamen, bachelor, master, akademisk utbildning, eftergymnasial utbildning) |
| yh | Vocational higher education (yrkeshögskola, YH, KY) |
| english_req | English language skill is required or asked for (not just: the ad is written in English) |
| swedish_req | Swedish language skill is required or asked for |
| communication | Communication skills or working with stakeholders (kommunikativ, intressenter, stakeholders) |

## Output format

One JSON object per line:

```json
{"ann_id": "D001", "skills": ["sql", "python", "statistics"], "notes": "R mentioned as 'R/Python'"}
```

`skills` lists every key labelled 1; all other keys are 0.

## Procedure and honesty notes

- Batches with ad text are recreated by `fetch` + `annotate_prep` into
  `data/annotation/texts/` (not committed, D16); the committed files hold ad ids and labels.
- The annotation was done by Claude (AI) sub-agents that saw only the ad and this
  guide, in batches, with no access to the dictionary or its output.
- Disagreements between the dictionary and the annotators were then read in context
  and adjudicated against this guide; both the raw annotations and the adjudicated
  labels are committed (`data/annotation/`), so the owner can audit them.
- A development sample (10 ads per year) is used to find and fix systematic
  dictionary errors. Reported precision and recall come from a separate test sample
  (15 ads per year), compared with the dictionary only after it was frozen.

## v1 clarifications (after the development sample, used for adjudication)

The annotators flagged these rules as ambiguous. They are settled as follows and
applied when disagreements on the test sample are adjudicated:

- **statistics:** any mention of statistics/statistik counts, including "statistik"
  meaning figures ("ta fram statistik", "webbstatistik") and a degree subject.
- **communication:** also counts when the ad asks the person to communicate,
  present or explain results/insights to others ("presentera insikter",
  "communicate results"). Plain teamwork or a "communication department" does not.
- **english_req / swedish_req:** a language asked for as a merit ("meriterande", "is
  a plus") counts; "not a requirement" does not; "one of the Nordic languages"
  without naming Swedish does not.
- **reporting:** producing reports counts; a reporting line ("reports to the CFO")
  does not.
- **degree:** a named degree or education at university level counts ("högskole-
  utbildning", "examen", MSc); "relevant utbildning" without level, students and
  "new graduates" do not.
