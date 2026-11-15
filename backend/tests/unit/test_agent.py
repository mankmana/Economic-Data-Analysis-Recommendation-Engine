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
