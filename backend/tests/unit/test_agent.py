import unittest

from backend.app.ai.agent import EconomicAgent, classify_query
from backend.app.config.settings import Settings
from backend.app.fred.client import FREDClient
from backend.app.models.domain import Series


def local_agent() -> EconomicAgent:
    return EconomicAgent(FREDClient(Settings(fred_live_data=False)))


class QueryClassificationTests(unittest.TestCase):
    def test_supported_question_routes(self) -> None:
        self.assertEqual(classify_query("What is the latest reported U.S. GDP?").name, "gdp_latest")
        self.assertEqual(classify_query("What is the current Core CPI inflation rate?").name, "cpi_latest")
        self.assertEqual(classify_query("What is the relationship between GDP growth and Core CPI inflation?").name, "comparison")
        self.assertEqual(classify_query("Generate a visualization comparing GDP growth and Core CPI inflation over time.").name, "comparison_chart")

    def test_month_based_history_preserves_exact_requested_window(self) -> None:
        intent = classify_query("How has GDP changed in the last 24 months?")
        self.assertEqual(intent.name, "gdp_history")
        self.assertEqual(intent.months, 24)
        self.assertEqual(intent.window_label, "24-month")

    def test_year_based_history_converts_to_months(self) -> None:
        intent = classify_query("How has Core CPI changed over the past five years?")
        self.assertEqual(intent.name, "cpi_history")
        self.assertEqual(intent.months, 60)
        self.assertEqual(intent.window_label, "5-year")


class EconomicAgentTests(unittest.TestCase):
    def test_unrelated_question_gets_default_grounded_response(self) -> None:
        result = local_agent().answer("What is the weather in San Jose today?")
        self.assertEqual(result.intent, "unsupported")
        self.assertIn("don't have grounded information", result.answer)
        self.assertIsNone(result.chart)

    def test_empty_question_gets_default_grounded_response(self) -> None:
        result = local_agent().answer("   ")
        self.assertEqual(result.intent, "unsupported")
        self.assertIn("Core CPI", result.answer)

    def test_missing_grounding_gets_data_unavailable_response(self) -> None:
        class EmptyClient:
            def get_series(self, series_id: str) -> Series:
                return Series(series_id, series_id, "", "", "local_grounding", "", [])

        result = EconomicAgent(EmptyClient()).answer("What is the latest reported U.S. GDP?")
        self.assertEqual(result.intent, "grounding_unavailable")
        self.assertIn("grounded data", result.answer)

    def test_latest_gdp_uses_saved_grounding(self) -> None:
        result = local_agent().answer("What is the latest reported U.S. GDP?")
        self.assertEqual(result.intent, "gdp_latest")
        self.assertIn("2026-Q3", result.answer)
        self.assertTrue(result.chart["series"][0]["values"])
        self.assertTrue(any("saved local grounding" in warning for warning in result.warnings))

    def test_gdp_history_does_not_replace_24_months_with_default_10_years(self) -> None:
        result = local_agent().answer("How has GDP changed in the last 24 months?")
        self.assertEqual(result.intent, "gdp_history")
        self.assertIn("requested 24-month window (8 quarterly periods)", result.answer)
        self.assertIn("available grounded result", result.answer)
        self.assertNotIn("10-year GDP window", result.answer)
        self.assertNotIn("I can't", result.answer)
        self.assertEqual(result.metrics[1].value, "+5.87%")
        self.assertIn("full requested 24-month", " ".join(result.warnings))

    def test_current_core_cpi_returns_inflation_warning_when_history_is_short(self) -> None:
        result = local_agent().answer("What is the current Core CPI inflation rate?")
        self.assertEqual(result.intent, "cpi_latest")
        self.assertNotIn("Unavailable", result.answer)
        self.assertIn("year-over-year Core CPI inflation", result.answer)

    def test_comparison_returns_two_chart_series(self) -> None:
        result = local_agent().answer("Generate a visualization comparing GDP growth and Core CPI inflation over time.")
        self.assertEqual(result.intent, "comparison_chart")
        self.assertEqual(len(result.chart["series"]), 2)
        self.assertIn("limited overlap", " ".join(result.warnings))


if __name__ == "__main__":
    unittest.main()
