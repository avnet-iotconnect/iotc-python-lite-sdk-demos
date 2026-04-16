#!/usr/bin/env bash

set -euo pipefail

ARM_KWS_REPO="${ARM_KWS_REPO:-$HOME/src/ML-zoo/models/keyword_spotting/ds_cnn_small/model_package_tf}"
DATA_DIR="${DATA_DIR:-$(cd "$(dirname "$0")" && pwd)/dataset-layout}"
WANTED_WORDS="${WANTED_WORDS:-command-1,command-2,command-3}"
TRAIN_DIR="${TRAIN_DIR:-$ARM_KWS_REPO/work/DS_CNN/DS_CNN_S/training}"
SUMMARIES_DIR="${SUMMARIES_DIR:-$ARM_KWS_REPO/work/DS_CNN/DS_CNN_S/retrain_logs}"

cd "$ARM_KWS_REPO"

python train.py \
  --data_url= \
  --data_dir "$DATA_DIR" \
  --wanted_words "$WANTED_WORDS" \
  --sample_rate 16000 \
  --clip_duration_ms 1000 \
  --window_size_ms 40 \
  --window_stride_ms 20 \
  --dct_coefficient_count 10 \
  --model_architecture ds_cnn \
  --model_size_info 5 64 10 4 2 2 64 3 3 1 1 64 3 3 1 1 64 3 3 1 1 64 3 3 1 1 \
  --background_frequency 0.8 \
  --background_volume 0.1 \
  --silence_percentage 10 \
  --unknown_percentage 10 \
  --how_many_training_steps 10000,10000,10000 \
  --learning_rate 0.0005,0.0001,0.00002 \
  --train_dir "$TRAIN_DIR" \
  --summaries_dir "$SUMMARIES_DIR"

printf '\nTraining complete.\n'
printf 'Best checkpoints: %s/best/\n' "$TRAIN_DIR"
printf 'TensorBoard logs: %s\n' "$SUMMARIES_DIR"
