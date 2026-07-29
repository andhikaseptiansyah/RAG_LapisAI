import unittest

from api.language import (
    answer_matches_requested_language,
    resolve_response_language,
)
from api.llm_shared import build_system_prompt, build_user_prompt


class ResponseLanguageTests(unittest.TestCase):
    def test_ui_selection_overrides_question_language(self) -> None:
        matrix = (
            ("What is the company policy?", "ID", "ID"),
            ("What is the company policy?", "EN", "EN"),
            ("Apa kebijakan perusahaan?", "ID", "ID"),
            ("Apa kebijakan perusahaan?", "EN", "EN"),
        )

        for question, selected_language, expected_language in matrix:
            with self.subTest(question=question, selected_language=selected_language):
                self.assertEqual(
                    resolve_response_language(question, selected_language),
                    expected_language,
                )

    def test_auto_mode_still_detects_language(self) -> None:
        self.assertEqual(resolve_response_language("Apa batas unggahan file?", "AUTO"), "ID")
        self.assertEqual(resolve_response_language("What is the upload limit?", "AUTO"), "EN")

    def test_wrong_language_answer_is_detected(self) -> None:
        english_answer = (
            "New employees serve a probation period of 3 months. "
            "A formal performance evaluation is conducted in week 12."
        )
        indonesian_answer = (
            "Karyawan baru menjalani masa percobaan selama 3 bulan. "
            "Evaluasi kinerja formal dilakukan pada minggu ke-12."
        )

        self.assertFalse(answer_matches_requested_language(english_answer, "ID"))
        self.assertTrue(answer_matches_requested_language(indonesian_answer, "ID"))
        self.assertFalse(answer_matches_requested_language(indonesian_answer, "EN"))
        self.assertTrue(answer_matches_requested_language(english_answer, "EN"))

    def test_language_neutral_answer_is_allowed(self) -> None:
        self.assertTrue(answer_matches_requested_language("PostgreSQL 16.", "ID"))
        self.assertTrue(answer_matches_requested_language("50 GB.", "EN"))

    def test_short_wrong_language_answer_is_rejected(self) -> None:
        self.assertFalse(answer_matches_requested_language("Two days per week.", "ID"))
        self.assertFalse(answer_matches_requested_language("Dua hari per minggu.", "EN"))
        self.assertTrue(answer_matches_requested_language("Dua hari per minggu.", "ID"))
        self.assertTrue(answer_matches_requested_language("Two days per week.", "EN"))

    def test_prompts_repeat_mandatory_output_language(self) -> None:
        id_prompt = build_system_prompt("ID") + build_user_prompt(
            "Berapa lama masa percobaan?",
            "New employees serve a probation period of 3 months.",
            "ID",
        )
        en_prompt = build_system_prompt("EN") + build_user_prompt(
            "Berapa lama masa percobaan?",
            "Masa percobaan berlangsung selama 3 bulan.",
            "EN",
        )

        self.assertIn("Bahasa Indonesia only", id_prompt)
        self.assertIn("BAHASA INDONESIA SAJA", id_prompt)
        self.assertIn("English only", en_prompt)
        self.assertIn("ENGLISH ONLY", en_prompt)


if __name__ == "__main__":
    unittest.main()
