import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rfp.answering import Answer, AnthropicAnswerer, ExtractiveAnswerer
from rfp.cli import answer_questionnaire
from rfp.guardrails import lint
from rfp.retrieval import Retriever, load_chunks

KNOWLEDGE = ROOT / "examples" / "knowledge"


class RetrievalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = Retriever(load_chunks(KNOWLEDGE))

    def test_chunks_by_heading(self):
        headings = {c.heading for c in self.retriever.chunks}
        self.assertTrue({"Encryption", "Single sign-on", "Forecasting"} <= headings)

    def test_top_hit_is_the_relevant_section(self):
        self.assertEqual(self.retriever.search("Is data encrypted at rest?")[0][0].heading, "Encryption")
        self.assertEqual(self.retriever.search("What forecast intervals are available?")[0][0].heading, "Forecasting")

    def test_unrelated_question_has_no_hits(self):
        self.assertEqual(self.retriever.search("on-premise deployment kubernetes"), [])


class AnsweringTest(unittest.TestCase):
    def test_extractive_reads_roadmap_and_negative_wording(self):
        retriever = Retriever(load_chunks(KNOWLEDGE))
        answerer = ExtractiveAnswerer()
        scim = answerer.answer("Do you support SCIM provisioning?", "", retriever.search("SCIM provisioning"))
        self.assertEqual(scim.short_answer, "Roadmap")
        history = answerer.answer("Do you keep field-level change history?", "", retriever.search("field-level change history"))
        self.assertEqual(history.short_answer, "No")

    def test_anthropic_answerer_sends_schema_and_parses_reply(self):
        payload = {"short_answer": "Yes", "long_answer": "Data is encrypted.", "confidence": "high", "source_ids": ["security#1"], "rationale": "stated"}
        seen = {}

        def create(**kwargs):
            seen.update(kwargs)
            return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(payload))])

        client = SimpleNamespace(messages=SimpleNamespace(create=create))
        chunks = Retriever(load_chunks(KNOWLEDGE)).search("encryption")
        answer = AnthropicAnswerer(client=client).answer("Is data encrypted?", "Security", chunks)
        self.assertEqual(answer.short_answer, "Yes")
        self.assertEqual(seen["model"], "claude-opus-5-5")
        self.assertEqual(seen["output_config"]["format"]["type"], "json_schema")
        self.assertIn("[security#1]", seen["messages"][0]["content"])


class GuardrailTest(unittest.TestCase):
    def test_flags_overclaims_and_unsourced_yes(self):
        flags = lint(Answer("Yes", "We guarantee 100% uptime.", "high", [], "", "test"))
        self.assertTrue(any("overclaim" in f for f in flags))
        self.assertIn("affirmative answer without a source", flags)

    def test_clean_answer_passes(self):
        self.assertEqual(lint(Answer("Yes", "Data is encrypted with AES-256.", "high", ["security#1"], "", "test")), [])


class LibraryTest(unittest.TestCase):
    def test_close_question_reuses_library_answer(self):
        library = [{"id": "L-1", "question": "What is your uptime commitment?", "short_answer": "Yes", "long_answer": "99.9% monthly."}]
        rows = [{"id": "Q1", "question": "What is the uptime commitment?"}]
        result = answer_questionnaire(rows, Retriever(load_chunks(KNOWLEDGE)), library, ExtractiveAnswerer())
        self.assertEqual(result[0]["origin"], "library")
        self.assertEqual(result[0]["needs_review"], "no")


if __name__ == "__main__":
    unittest.main()
