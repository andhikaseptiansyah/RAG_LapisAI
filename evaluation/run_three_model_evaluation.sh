#!/usr/bin/env bash
set -euo pipefail

python evaluation/generation/run_three_model_evaluation.py \
  --english evaluation/datasets/qna_english_user.csv \
  --indonesian evaluation/datasets/qna_indonesia_user.csv \
  "$@"
