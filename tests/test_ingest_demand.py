from gb_demand_forecast.ingest.demand import parse_year, select_years


def test_parse_year_finds_year():
    assert parse_year("Historic Demand Data 2025") == 2025


def test_parse_year_returns_none_without_year():
    assert parse_year("Data description") is None


def test_select_years_filters_by_range_and_format():
    resources = [
        {"name": "Historic Demand Data 2017", "format": "CSV", "url": "u2017"},
        {"name": "Historic Demand Data 2018", "format": "CSV", "url": "u2018"},
        {"name": "Historic Demand Data 2019", "format": "csv", "url": "u2019"},
        {"name": "Guidance 2019", "format": "PDF", "url": "pdf"},
    ]
    assert select_years(resources, 2018, 2019) == {2018: "u2018", 2019: "u2019"}
