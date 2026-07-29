"""Regression checks for truncated/multi-part Ollama answers."""

from api.ollama_client import (
    _answer_numeric_values,
    _is_likely_incomplete_answer,
    _question_expected_numeric_values,
)


def main() -> None:
    question = (
        "Berapa total pendapatan perusahaan sepanjang FY2025 dan berapa "
        "persentase margin laba bersihnya?"
    )

    assert _question_expected_numeric_values(question) >= 2
    assert _is_likely_incomplete_answer(question, "Total pendapatan perusahaan")
    assert _is_likely_incomplete_answer(
        question,
        "Total pendapatan perusahaan adalah IDR 158 miliar.",
    )

    complete = (
        "Total pendapatan perusahaan sepanjang FY2025 adalah IDR 158 miliar, "
        "dengan margin laba bersih sebesar 14%."
    )
    assert len(_answer_numeric_values(complete)) >= 2
    assert not _is_likely_incomplete_answer(question, complete)
    assert _is_likely_incomplete_answer("Jelaskan hasilnya", complete, "length")

    print("Ollama incomplete-answer regression tests passed.")


if __name__ == "__main__":
    main()
