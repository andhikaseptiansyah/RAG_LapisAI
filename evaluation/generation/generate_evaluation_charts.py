"""Generate presentation-ready PNG diagrams from the three-model comparison."""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np


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
    bars = ax.barh(positions, values)
    ax.set_yticks(positions, labels)
    ax.invert_yaxis()
    ax.set_xlabel(x_label)
    ax.set_title(title, loc="left", fontsize=16, fontweight="bold", pad=18)
    fig.text(0.125, 0.91, subtitle, fontsize=10)
    ax.grid(axis="x", alpha=0.2)
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
    fig.tight_layout(rect=(0, 0, 1, 0.89))
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
    maximum: float = 100.0,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 6.2))
    x = np.arange(len(models))
    width = 0.8 / max(len(series), 1)
    for index, (label, values) in enumerate(series):
        offset = (index - (len(series) - 1) / 2) * width
        bars = ax.bar(x + offset, values, width, label=label)
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + maximum * 0.012,
                f"{value:.1f}",
                ha="center",
                va="bottom",
                fontsize=8,
                rotation=0,
            )
    ax.set_xticks(x, models)
    ax.set_ylim(0, maximum)
    ax.set_ylabel(y_label)
    ax.set_title(title, loc="left", fontsize=16, fontweight="bold", pad=18)
    fig.text(0.125, 0.91, subtitle, fontsize=10)
    ax.grid(axis="y", alpha=0.2)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=min(4, len(series)), frameon=False)
    fig.tight_layout(rect=(0, 0.06, 1, 0.89))
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def model_label(row: dict[str, str]) -> str:
    provider = str(row.get("Model") or "").title()
    concrete = str(row.get("Model Name") or "").strip()
    return f"{provider}\n{concrete}" if concrete else provider


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

    save_bar(
        output_dir / "01_overall_model_score.png",
        "Skor keseluruhan model",
        "Rata-rata makro bilingual: 35% jawaban, 30% grounding, 20% retrieval, 15% keamanan. Latensi tidak masuk skor.",
        models,
        [number(row.get("overall_score")) for row in overall],
        x_label="Skor (0–100)",
        maximum=100,
    )

    save_grouped(
        output_dir / "02_retrieval_quality.png",
        "Kualitas retrieval",
        "Metrik tingkat dokumen dari satu snapshot retrieval yang sama untuk semua model.",
        models,
        [
            ("Recall@K", [number(row.get("recall_at_k")) * 100 for row in overall]),
            ("Hit@K", [number(row.get("hit_at_k")) * 100 for row in overall]),
            ("MRR", [number(row.get("mrr")) * 100 for row in overall]),
        ],
        y_label="Skor (%)",
    )

    save_grouped(
        output_dir / "03_answer_and_grounding.png",
        "Kualitas jawaban dan grounding",
        "Kemiripan jawaban, relevansi semantik, faithfulness bukti, dan ketepatan sitasi.",
        models,
        [
            ("Token F1", [number(row.get("token_f1")) * 100 for row in overall]),
            ("Keyword", [number(row.get("keyword_coverage")) * 100 for row in overall]),
            ("Relevance", [number(row.get("answer_relevance_1_to_5")) / 5 * 100 for row in overall]),
            ("Faithfulness", [number(row.get("faithfulness_1_to_5")) / 5 * 100 for row in overall]),
            ("Citation", [number(row.get("citation_accuracy")) * 100 for row in overall]),
        ],
        y_label="Skor (%)",
    )

    save_grouped(
        output_dir / "04_safety_quality.png",
        "Keamanan dan kendali kegagalan",
        "Nilai lebih tinggi lebih baik. Hallucination dan kegagalan dibalik menjadi skor keberhasilan aman.",
        models,
        [
            ("Answerable success", [(1 - number(row.get("false_refusal_rate"))) * 100 for row in overall]),
            ("Unanswerable safety", [number(row.get("unanswerable_safety_rate")) * 100 for row in overall]),
            ("No hallucination", [(1 - number(row.get("hallucination_rate"))) * 100 for row in overall]),
            ("Generation success", [(1 - number(row.get("generation_failure_rate"))) * 100 for row in overall]),
        ],
        y_label="Skor keberhasilan aman (%)",
    )

    save_bar(
        output_dir / "05_average_latency.png",
        "Rata-rata latensi respons",
        "Waktu respons end-to-end dari sisi klien. Lebih rendah lebih baik.",
        models,
        [number(row.get("average_response_time_ms")) / 1000 for row in overall],
        x_label="Detik",
        suffix=" s",
    )

    language_rows = [row for row in rows if row.get("Scope") in {"EN", "ID"}]
    language_series: list[tuple[str, list[float]]] = []
    for scope in ("EN", "ID"):
        indexed = {str(row.get("Model") or ""): row for row in language_rows if row.get("Scope") == scope}
        language_series.append((scope, [number(indexed.get(str(row.get("Model") or ""), {}).get("overall_score")) for row in overall]))
    save_grouped(
        output_dir / "06_language_comparison.png",
        "Performa Inggris dan Indonesia",
        "Rubrik yang sama diterapkan secara terpisah pada setiap bahasa.",
        models,
        language_series,
        y_label="Skor keseluruhan (0–100)",
    )

    images = sorted(output_dir.glob("*.png"))
    table_headers = ["Model", "Overall", "Answer", "Grounding", "Retrieval", "Safety", "Avg latency (ms)"]
    table_rows = [
        [
            html.escape(str(row.get("Model") or "")),
            row.get("overall_score"),
            row.get("answer_quality_score"),
            row.get("grounding_score"),
            row.get("retrieval_score"),
            row.get("safety_score"),
            row.get("average_response_time_ms"),
        ]
        for row in overall
    ]
    report = [
        "<!doctype html><html><head><meta charset='utf-8'><title>LapisAI 3-Model Evaluation</title>",
        "<style>body{font-family:Arial,sans-serif;max-width:1180px;margin:36px auto;padding:0 20px;color:#172033}h1{margin-bottom:6px}p{color:#526078}img{width:100%;margin:18px 0 36px;border:1px solid #dfe5ef;border-radius:12px}table{border-collapse:collapse;width:100%;margin:24px 0}th,td{border-bottom:1px solid #dfe5ef;padding:10px;text-align:left}th{background:#f4f7fb}</style></head><body>",
        "<h1>LapisAI three-model evaluation</h1>",
        "<p>Ollama, Gemini, and Groq compared on the same bilingual question set and retrieval evidence.</p>",
        "<table><thead><tr>" + "".join(f"<th>{header}</th>" for header in table_headers) + "</tr></thead><tbody>",
    ]
    for row in table_rows:
        report.append("<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>")
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
