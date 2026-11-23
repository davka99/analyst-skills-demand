import pytest

from adskills.titles import PRIMARY, classify_headline, in_population


@pytest.mark.parametrize(
    "headline, expected",
    [
        ("Dataanalytiker till Region Stockholm", "data_analyst"),
        ("Data Analyst", "data_analyst"),
        ("Senior Data-analytiker", "data_analyst"),
        ("Junior data analyst – e-commerce", "data_analyst"),
        ("Data & BI Analyst", "bi_analyst"),
        ("Analytiker inom data och statistik", "data_analyst"),
        ("Financial Data Analyst", "data_analyst"),
        ("BI-analytiker", "bi_analyst"),
        ("BI Analyst till växande bolag", "bi_analyst"),
        ("Business Intelligence-analytiker", "bi_analyst"),
        ("Business Intelligence Analyst", "bi_analyst"),
        ("Insights Analyst", "analytics_analyst"),
        ("Web analyst", "analytics_analyst"),
        ("Webbanalytiker", "analytics_analyst"),
        ("Kundanalytiker", "analytics_analyst"),
        ("Försäljningsanalytiker", "analytics_analyst"),
        ("Marketing Analyst", "analytics_analyst"),
        ("HR-analytiker", "analytics_analyst"),
        ("BI-utvecklare", "bi_developer"),
        ("BI Developer", "bi_developer"),
        ("Data Scientist", "data_scientist"),
        ("Dataingenjör", "data_engineer"),
        ("Data Engineer", "data_engineer"),
        ("Statistiker", "statistician"),
        ("Online Data Analyst - Swedish", "online_rater"),
        ("Master Data Analyst", "master_data"),
        ("Masterdata-analytiker", "master_data"),
    ],
)
def test_classify_known_titles(headline, expected):
    assert classify_headline(headline) == expected


@pytest.mark.parametrize(
    "headline",
    [
        "Analytiker",
        "Kreditanalytiker",
        "Finansanalytiker",
        "Systemanalytiker",
        "Verksamhetsanalytiker",
        "Business Analyst",
        "Utredare/analytiker inom socialtjänst",
        "Analytiker i datadriven verksamhet",  # "datadriven" is not "data"
        "Lärare i matematik",
        "Busschaufför",
        "Online Opportunity - Online Data Analyst - Norwegian (NO)",
        "Master Data Analyst - Logistics & Supply Chain",
        "Biträdande förskolechef",  # "bi" inside a word
        "",
        None,
    ],
)
def test_not_in_population(headline):
    assert not in_population(headline)


def test_neighbour_roles_not_in_population():
    for h in ("BI-utvecklare", "Data Scientist", "Data Engineer", "Statistiker"):
        assert classify_headline(h) is not None
        assert not in_population(h)


def test_combined_title_counts_as_analyst():
    # A combined title that includes a data-analyst role is in the population.
    assert classify_headline("Data Scientist / Data Analyst") == "data_analyst"


def test_primary_categories():
    assert PRIMARY == {"data_analyst", "bi_analyst", "analytics_analyst"}


def test_dash_variants_and_case():
    assert classify_headline("DATA–ANALYTIKER") == "data_analyst"
    assert classify_headline("bi‑analytiker") == "bi_analyst"
