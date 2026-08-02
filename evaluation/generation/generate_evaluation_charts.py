"""Generate presentation-ready charts from a one-or-more-model evaluation."""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


PALETTE = ("#2F5D8C", "#D79A2B", "#718355", "#7A5C99", "#4F7C78")
GRID_COLOR = "#AEB8C5"


def number(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Comparison CSV is empty: {path}")
    return rows


def overall_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    macro = [row for row in rows if row.get("Scope") == "MACRO"]
    return macro or [row for row in rows if row.get("Scope") == "ALL"]


def save_bar(
    output: Path,
    title: str,
    subtitle: str,
    labels: list[str],
    values: list[float],
    *,
    x_label: str,
    maximum: float | None = None,
    suffix: str = "",
) -> None:
    fig, ax = plt.subplots(figsize=(10, 5.6))
    positions = np.arange(len(labels))
    bars = ax.barh(positions, values, color=PALETTE[0])
    ax.set_yticks(positions, labels)
    ax.invert_yaxis()
    ax.set_xlabel(x_label)
    fig.suptitle(title, x=0.125, y=0.97, ha="left", fontsize=16, fontweight="bold")
    fig.text(0.125, 0.91, subtitle, fontsize=10, color="#526078")
    ax.grid(axis="x", alpha=0.35, color=GRID_COLOR)
    if maximum is not None:
        ax.set_xlim(0, maximum)
    for bar, value in zip(bars, values):
        ax.text(
            bar.get_width() + ((maximum or max(values or [1])) * 0.012),
            bar.get_y() + bar.get_height() / 2,
            f"{value:.1f}{suffix}",
            va="center",
            fontsize=10,
        )
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def save_grouped(
    output: Path,
    title: str,
    subtitle: str,
    models: list[str],
    series: list[tuple[str, list[float]]],
    *,
    y_label: str,
    maximum: float | None = 100.0,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 6.2))
    x = np.arange(len(models))
    width = 0.8 / max(len(series), 1)
    observed_maximum = max(
        (value for _, values in series for value in values),
        default=1.0,
    )
    plot_maximum = maximum or max(observed_maximum * 1.22, 1.0)
    for index, (label, values) in enumerate(series):
        offset = (index - (len(series) - 1) / 2) * width
        bars = ax.bar(
            x + offset,
            values,
            width,
            label=label,
            color=PALETTE[index % len(PALETTE)],
        )
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + plot_maximum * 0.012,
                f"{value:.1f}",
                ha="center",
                va="bottom",
                fontsize=8,
                rotation=0,
            )
    ax.set_xticks(x, models)
    ax.set_ylim(0, plot_maximum)
    ax.set_ylabel(y_label)
    fig.suptitle(title, x=0.125, y=0.97, ha="left", fontsize=16, fontweight="bold")
    fig.text(0.125, 0.91, subtitle, fontsize=10, color="#526078")
    ax.grid(axis="y", alpha=0.35, color=GRID_COLOR)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=min(4, len(series)), frameon=False)
    fig.tight_layout(rect=(0, 0.06, 1, 0.86))
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def model_label(row: dict[str, str]) -> str:
    provider = str(row.get("Model") or "").title()
    concrete = str(row.get("Model Name") or "").strip()
    return f"{provider}\n{concrete}" if concrete else provider


def comparison_score(row: dict[str, str]) -> float:
    """Use the complete composite, or its explicitly labelled deterministic fallback."""
    if row.get("overall_score") not in (None, ""):
        return number(row.get("overall_score"))
    return number(row.get("deterministic_score"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    rows = load_rows(args.comparison.resolve())
    overall = overall_rows(rows)
    if not overall:
        raise ValueError("No Scope=ALL rows found in comparison CSV")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    models = [model_label(row) for row in overall]
    uses_deterministic_fallback = any(
        row.get("overall_score") in (None, "")
        for row in overall
    )
    language_sets_are_unpaired = any(
        row.get("Language Comparison Status")
        == "descriptive_only_unpaired_targets"
        for row in overall
    )

    save_bar(
        output_dir / "01_overall_model_score.png",
        (
            "Skor diagnostik deterministik"
            if uses_deterministic_fallback
            else "Skor keseluruhan model"
        ),
        (
            "LLM judge tidak lengkap; grafik memakai deterministic_score dan tidak menyatakannya sebagai overall."
            if uses_deterministic_fallback
            else "Rata-rata makro bilingual: 35% jawaban, 30% grounding, 20% retrieval, 15% keamanan. Latensi tidak masuk skor."
        ),
        models,
        [comparison_score(row) for row in overall],
        x_label="Skor (0–100)",
        maximum=100,
    )

    retrieval_series = [
        ("Recall@K", [number(row.get("recall_at_k")) * 100 for row in overall]),
        ("Hit@K", [number(row.get("hit_at_k")) * 100 for row in overall]),
        ("MRR", [number(row.get("mrr")) * 100 for row in overall]),
    ]
    if any(row.get("ndcg_at_k") not in (None, "") for row in overall):
        retrieval_series.append(
            ("NDCG@K", [number(row.get("ndcg_at_k")) * 100 for row in overall])
        )
    save_grouped(
        output_dir / "02_retrieval_quality.png",
        "Kualitas retrieval",
        "Metrik tingkat dokumen dari satu snapshot retrieval yang sama untuk semua model.",
        models,
        retrieval_series,
        y_label="Skor (%)",
    )

    answer_grounding_series = [
        ("Token F1", [number(row.get("token_f1")) * 100 for row in overall]),
        ("Keyword", [number(row.get("keyword_coverage")) * 100 for row in overall]),
        (
            "Citation F1",
            [
                number(
                    row.get("citation_f1")
                    if row.get("citation_f1") not in (None, "")
                    else row.get("citation_accuracy")
                ) * 100
                for row in overall
            ],
        ),
    ]
    if not uses_deterministic_fallback:
        answer_grounding_series[2:2] = [
            (
                "Relevance",
                [
                    number(row.get("answer_relevance_1_to_5")) / 5 * 100
                    for row in overall
                ],
            ),
            (
                "Faithfulness",
                [
                    number(row.get("faithfulness_1_to_5")) / 5 * 100
                    for row in overall
                ],
            ),
        ]
    save_grouped(
        output_dir / "03_answer_and_grounding.png",
        "Kualitas jawaban dan grounding",
        (
            "Metrik deterministik; relevance dan faithfulness tidak ditampilkan karena judge belum lengkap."
            if uses_deterministic_fallback
            else "Kemiripan jawaban, relevansi semantik, faithfulness bukti, dan ketepatan sitasi."
        ),
        models,
        answer_grounding_series,
        y_label="Skor (%)",
    )

    safety_series = [
        (
            "Answerable success",
            [
                (1 - number(row.get("false_refusal_rate"))) * 100
                for row in overall
            ],
        ),
        (
            "Unanswerable safety",
            [
                number(row.get("unanswerable_safety_rate")) * 100
                for row in overall
            ],
        ),
        (
            "Pipeline success",
            [
                (
                    1
                    - number(
                        row.get("pipeline_failure_rate")
                        if row.get("pipeline_failure_rate") not in (None, "")
                        else row.get("generation_failure_rate")
                    )
                ) * 100
                for row in overall
            ],
        ),
        (
            "Model/provider success",
            [
                (1 - number(row.get("generation_failure_rate"))) * 100
                for row in overall
            ],
        ),
    ]
    if not uses_deterministic_fallback:
        safety_series.insert(
            2,
            (
                "No hallucination",
                [
                    (1 - number(row.get("hallucination_rate"))) * 100
                    for row in overall
                ],
            ),
        )
    save_grouped(
        output_dir / "04_safety_quality.png",
        "Keamanan dan kendali kegagalan",
        (
            "Nilai lebih tinggi lebih baik; hallucination tidak ditampilkan karena judge belum lengkap."
            if uses_deterministic_fallback
            else "Nilai lebih tinggi lebih baik. Hallucination dan kegagalan dibalik menjadi skor keberhasilan aman."
        ),
        models,
        safety_series,
        y_label="Skor keberhasilan aman (%)",
    )

    save_grouped(
        output_dir / "05_average_latency.png",
        "Rata-rata komponen latensi",
        "Retrieval dan panggilan generation diukur terpisah; sequential E2E adalah jumlah estimasi keduanya. Lebih rendah lebih baik.",
        models,
        [
            (
                "Retrieval",
                [
                    number(row.get("average_retrieval_time_ms")) / 1000
                    for row in overall
                ],
            ),
            (
                "Generation API call",
                [
                    number(row.get("average_response_time_ms")) / 1000
                    for row in overall
                ],
            ),
            (
                "Estimated sequential E2E",
                [
                    number(row.get("average_estimated_sequential_e2e_ms")) / 1000
                    for row in overall
                ],
            ),
        ],
        y_label="Detik",
        maximum=None,
    )

    language_rows = [row for row in rows if row.get("Scope") in {"EN", "ID"}]
    language_series: list[tuple[str, list[float]]] = []
    for scope in ("EN", "ID"):
        indexed = {str(row.get("Model") or ""): row for row in language_rows if row.get("Scope") == scope}
        language_series.append(
            (
                scope,
                [
                    comparison_score(indexed.get(str(row.get("Model") or ""), {}))
                    for row in overall
                ],
            )
        )
    save_grouped(
        output_dir / "06_language_comparison.png",
        (
            "Skor per dataset bahasa"
            if language_sets_are_unpaired
            else "Performa Inggris dan Indonesia"
        ),
        (
            "Deskriptif saja: target pertanyaan/sumber EN dan ID tidak ekuivalen, sehingga selisih bukan efek bahasa murni."
            if language_sets_are_unpaired
            else "Menggunakan deterministic_score karena LLM judge tidak lengkap."
            if uses_deterministic_fallback
            else "Rubrik yang sama diterapkan secara terpisah pada setiap bahasa."
        ),
        models,
        language_series,
        y_label=(
            "Skor diagnostik deterministik (0–100)"
            if uses_deterministic_fallback
            else "Skor keseluruhan (0–100)"
        ),
    )

    images = sorted(output_dir.glob("*.png"))
    model_count = len(overall)
    report_statuses = {
        str(row.get("Report Status") or "UNKNOWN") for row in overall
    }
    report_status = (
        next(iter(report_statuses))
        if len(report_statuses) == 1
        else "MIXED"
    )
    table_headers = [
        "Model",
        "Report status",
        "Score status",
        "Overall",
        "Deterministic",
        "Answer",
        "Grounding",
        "Retrieval",
        "Safety",
        "Judge coverage",
        "Avg generation call (ms)",
        "Estimated E2E (ms)",
    ]
    table_rows = [
        [
            row.get("Model"),
            row.get("Report Status"),
            row.get("score_status"),
            row.get("overall_score"),
            row.get("deterministic_score"),
            row.get("answer_quality_score"),
            row.get("grounding_score"),
            row.get("retrieval_score"),
            row.get("safety_score"),
            row.get("judge_coverage"),
            row.get("average_response_time_ms"),
            row.get("average_estimated_sequential_e2e_ms"),
        ]
        for row in overall
    ]
    dashboard_title = (
        "LapisAI 1-model evaluation"
        if model_count == 1
        else f"LapisAI {model_count}-model comparison"
    )
    report = [
        f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(dashboard_title)}</title>",
        "<style>body{font-family:Arial,sans-serif;max-width:1180px;margin:36px auto;padding:0 20px;color:#172033}h1{margin-bottom:6px}p{color:#526078}.status{padding:12px 16px;border-radius:10px;background:#fff4d6;color:#704b00;font-weight:700;margin:18px 0}.status.final{background:#e5f7ed;color:#165c36}img{width:100%;margin:18px 0 36px;border:1px solid #dfe5ef;border-radius:12px}table{border-collapse:collapse;width:100%;margin:24px 0}th,td{border-bottom:1px solid #dfe5ef;padding:10px;text-align:left}th{background:#f4f7fb}</style></head><body>",
        f"<h1>{html.escape(dashboard_title)}</h1>",
        f"<div class='status{' final' if report_status == 'FINAL_ELIGIBLE' else ''}'>Report status: {html.escape(report_status)}</div>",
        "<p>Evaluation uses source-locked retrieval evidence. A diagnostic report must not be presented as a final holdout result.</p>",
        "<table><thead><tr>" + "".join(f"<th>{header}</th>" for header in table_headers) + "</tr></thead><tbody>",
    ]
    for row in table_rows:
        report.append(
            "<tr>"
            + "".join(
                f"<td>{html.escape(str(value))}</td>" for value in row
            )
            + "</tr>"
        )
    report.append("</tbody></table>")
    for image in images:
        report.append(f"<img src='{html.escape(image.name)}' alt='{html.escape(image.stem)}'>")
    report.append("</body></html>")
    (output_dir / "evaluation_dashboard.html").write_text("\n".join(report), encoding="utf-8")

    print(f"Charts generated: {len(images)}")
    for image in images:
        print(image)
    print(output_dir / "evaluation_dashboard.html")


if __name__ == "__main__":
    main()
