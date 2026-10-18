import unittest
from editorial import editorial_context

class EditorialTests(unittest.TestCase):
    def test_inflation_country_specific(self):
        article={"title":"Inflation update","summary":"Consumer price index"}
        ro=editorial_context(article,"RO")
        fr=editorial_context(article,"FR")
        self.assertEqual(ro["topic"],"inflation")
        self.assertIn("BNR",ro["impact"])
        self.assertIn("欧元区",fr["impact"])
    def test_major_exceptional_title(self):
        ctx=editorial_context({"title":"Emergency rate cut announced","summary":""},"RO")
        self.assertTrue(ctx["major"])

    def test_routine_rates_not_major(self):
        ctx=editorial_context({"title":"Interest rate decision","summary":""},"FR")
        self.assertEqual(ctx["topic"],"monetary")
        self.assertFalse(ctx["major"])

    def test_partial_word_not_match(self):
        ctx=editorial_context({"title":"Reinflationary analysis","summary":""},"FR")
        self.assertEqual(ctx["topic"],"other")

    def test_unknown_topic_no_claim(self):
        ctx=editorial_context({"title":"Administrative update","summary":""},"FR")
        self.assertEqual(ctx["topic"],"other")
        self.assertFalse(ctx["major"])
