import pytest

from adskills.skills import SKILL_KEYS, find_skills, matches, skill_matrix


def has(text, key):
    return key in find_skills(text)


@pytest.mark.parametrize(
    "text, key",
    [
        ("Goda Excelkunskaper är ett krav", "excel"),
        ("Du har erfarenhet av MS Excel", "excel"),
        ("Erfarenhet av SQL-frågor", "sql"),
        ("Kunskaper i T-SQL och SQL Server", "sql"),
        ("PostgreSQL eller MySQL", "sql"),
        ("Pythonprogrammering är meriterande", "python"),
        ("Erfarenhet av Python och R", "r"),
        ("Python, R eller SAS", "r"),
        ("R/Python", "r"),
        ("Vi använder RStudio", "r"),
        ("R-programmering", "r"),
        ("programmeringsspråk som R", "r"),
        ("Erfarenhet av SAS är meriterande", "sas"),
        ("SPSS eller Stata", "spss"),
        ("SPSS eller Stata", "stata"),
        ("Makron i VBA", "vba"),
        ("Power BI och DAX", "power_bi"),
        ("PowerBI", "power_bi"),
        ("Power BI och DAX", "dax"),
        ("Tableau eller Qlik Sense", "tableau"),
        ("QlikView", "qlik"),
        ("Looker Studio", "looker"),
        ("Microsoft Azure", "azure"),
        ("AWS eller GCP", "aws"),
        ("BigQuery", "gcp"),
        ("Snowflake och dbt", "snowflake"),
        ("Snowflake och dbt", "dbt"),
        ("Databricks", "databricks"),
        ("PySpark", "spark"),
        ("versionshantering med Git", "git"),
        ("goda statistikkunskaper", "statistics"),
        ("statistical modelling", "statistics"),
        ("maskininlärning", "machine_learning"),
        ("machine learning", "machine_learning"),
        ("budget och prognoser", "forecasting"),
        ("A/B-tester", "experimentation"),
        ("A/B testing", "experimentation"),
        ("ETL-processer", "etl_dw"),
        ("datalager", "etl_dw"),
        ("visualisera data", "visualization"),
        ("bygga dashboards", "visualization"),
        ("rapportering till ledningen", "reporting"),
        ("Vi arbetar med AI", "ai_any"),
        ("generativ AI", "genai"),
        ("LLM:er och ChatGPT", "genai"),
        ("Microsoft Copilot", "genai"),
        ("akademisk examen inom statistik", "degree"),
        ("Master's degree in economics", "degree"),
        ("Examen från yrkeshögskola", "yh"),
        ("YH-utbildning inom data", "yh"),
        ("svenska och engelska i tal och skrift", "english_req"),
        ("svenska och engelska i tal och skrift", "swedish_req"),
        ("You are fluent in English", "english_req"),
        ("engelska och svenska i tal och skrift", "english_req"),
        ("engelska och svenska i tal och skrift", "swedish_req"),
        ("fluent in Swedish and English", "english_req"),
        ("Du är kommunikativ", "communication"),
        ("work closely with stakeholders", "communication"),
        ("Engelska är meriterande", "english_req"),
        ("du uttrycker dig väl i både svenska och engelska", "swedish_req"),  # asked for as a merit counts (guide)
        ("SQL, Python, or R is a plus", "r"),
        ("PBI reports", "power_bi"),
        ("webbstatistik", "statistics"),
        ("bygga nya rapporter", "reporting"),
        ("veckorapporter", "reporting"),
        ("relevant högskoleutbildning", "degree"),
        ("MSc in statistics", "degree"),
        ("Data Vault och DBT", "etl_dw"),
        ("du kan presentera dina insikter", "communication"),
    ],
)
def test_positive(text, key):
    assert has(text, key), (text, key, find_skills(text))


@pytest.mark.parametrize(
    "text, key",
    [
        ("Excellent communication", "excel"),
        ("NoSQL databases", "sql"),
        ("R&D department", "r"),
        ("Vi erbjuder rapportering", "r"),
        ("Python och rutiner", "r"),
        ("Python and reporting", "r"),
        ("Flyg med SAS Scandinavian Airlines", "sas"),
        ("Kassa", "sas"),
        ("Daxberg AB", "dax"),
        ("Laws and regulations", "aws"),
        ("Digital transformation", "git"),
        ("Fair play", "ai_any"),
        ("Hej, jag heter Kai", "ai_any"),
        ("Master data management", "degree"),
        ("Vi arbetar med experimentell fysik", "experimentation"),
        ("You will report to our CTO", "reporting"),
        ("du rapporterar till marknadschefen", "reporting"),
        ("reporting to the head of analytics", "reporting"),
        ("som analytiker rapporterar du till marknadschefen", "reporting"),
        ("High degree of expertise with SQL", "degree"),
        ("den svenska bostadsmarknaden", "swedish_req"),
        ("Swedish is not a requirement", "swedish_req"),
        ("marknads- och kommunikationsavdelning", "communication"),
    ],
)
def test_negative(text, key):
    assert not has(text, key), (text, key, matches(key, text))


def test_keys_unique_and_matrix_shape():
    assert len(SKILL_KEYS) == len(set(SKILL_KEYS))
    m = skill_matrix(["SQL och Python", "", None])
    assert list(m.columns) == list(SKILL_KEYS)
    assert m.shape == (3, len(SKILL_KEYS))
    assert m.loc[0, "sql"] and m.loc[0, "python"] and not m.loc[1].any() and not m.loc[2].any()


def test_html_is_stripped():
    assert has("<p>Erfarenhet av <b>Power&nbsp;BI</b></p>", "power_bi")
