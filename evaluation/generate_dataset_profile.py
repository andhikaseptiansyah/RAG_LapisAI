"""Create a factual diagram of the evaluation dataset before model execution."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def counts(path: Path) -> tuple[int, int]:
    answerable = 0
    unanswerable = 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("answerable") or "").strip().casefold() in {"true", "1", "yes", "y", "ya"}:
                answerable += 1
            else:
                unanswerable += 1
    return answerable, unanswerable


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--english", type=Path, required=True)
    parser.add_argument("--indonesian", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    en = counts(args.english.resolve())
    ind = counts(args.indonesian.resolve())
    labels = ["Inggris", "Indonesia"]
    answerable = [en[0], ind[0]]
    unanswerable = [en[1], ind[1]]
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    ax.bar(x, answerable, label="Dapat dijawab")
    ax.bar(x, unanswerable, bottom=answerable, label="Tidak dapat dijawab")
    ax.set_xticks(x, labels)
    ax.set_ylabel("Jumlah pertanyaan")
    ax.set_title("Dataset evaluasi LapisAI", loc="left", fontsize=16, fontweight="bold", pad=18)
    fig.text(0.125, 0.91, f"89 pertanyaan unik: {sum(answerable)} dapat dijawab dan {sum(unanswerable)} tidak dapat dijawab.", fontsize=10)
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False)
    for index, (yes, no) in enumerate(zip(answerable, unanswerable)):
        ax.text(index, yes / 2, str(yes), ha="center", va="center", fontsize=11)
        ax.text(index, yes + no / 2, str(no), ha="center", va="center", fontsize=11)
        ax.text(index, yes + no + 1, str(yes + no), ha="center", fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.89))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output.resolve(), dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
