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
    def test_unknown_topic_no_claim(self):
        ctx=editorial_context({"title":"Administrative update","summary":""},"FR")
        self.assertEqual(ctx["topic"],"other")
        self.assertFalse(ctx["major"])
