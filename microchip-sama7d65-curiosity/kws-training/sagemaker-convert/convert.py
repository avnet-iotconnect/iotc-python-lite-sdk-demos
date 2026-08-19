# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
from __future__ import annotations

import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import tensorflow as tf
import torch

INPUT_DIR = Path(os.getenv("SM_PROCESSING_INPUT", "/opt/ml/processing/input"))
OUTPUT_DIR = Path(os.getenv("SM_PROCESSING_OUTPUT", "/opt/ml/processing/output"))
WEIGHTS_NAME = os.getenv("WEIGHTS_NAME", "model-state.pt").strip() or "model-state.pt"
PACKAGE_NAME_OVERRIDE = os.getenv("PACKAGE_NAME", "").strip()
PACKAGE_DISPLAY_NAME = os.getenv("PACKAGE_DISPLAY_NAME", "").strip()

MODEL_FILE_NAME = "model.tflite"
LABELS_FILE_NAME = "labels.txt"
PACKAGE_INFO_FILE_NAME = "package-info.json"
CONVERSION_RESULT_FILE_NAME = "conversion-result.json"
SPECIAL_LABELS = {"_silence_", "_unknown_"}
DEFAULT_DSCNN_ARCHITECTURE = "ds-cnn-mfcc"

INSTALL_SCRIPT = """#!/bin/sh
set -e

mkdir -p /opt/demo/models
cp -f ./models/* /opt/demo/models/
if [ -f /opt/demo/models/model.tflite ] && [ ! -f /opt/demo/models/ds_cnn_s_quantized.tflite ]; then
  cp -f /opt/demo/models/model.tflite /opt/demo/models/ds_cnn_s_quantized.tflite
fi
if [ -f /opt/demo/models/ds_cnn_s_quantized.tflite ] && [ ! -f /opt/demo/models/model.tflite ]; then
  cp -f /opt/demo/models/ds_cnn_s_quantized.tflite /opt/demo/models/model.tflite
fi
echo "Installed model assets into /opt/demo/models"
"""


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return normalized.strip("-") or "kws-model"


def find_input_file(file_name: str) -> Path:
    candidate = INPUT_DIR / file_name
    if candidate.is_file():
        return candidate
    matches = sorted(INPUT_DIR.rglob(file_name))
    if matches:
        return matches[0]
    raise FileNotFoundError(f"Could not find {file_name} under {INPUT_DIR}")


def try_find_input_file(file_name: str) -> Path | None:
    try:
        return find_input_file(file_name)
    except FileNotFoundError:
        return None


def load_state_artifact(path: Path) -> tuple[dict[str, torch.Tensor], dict[str, Any]]:
    payload = torch.load(path, map_location="cpu")
    if not isinstance(payload, dict) or "state_dict" not in payload:
        raise RuntimeError(f"Unsupported state artifact: {path}")
    state_dict = payload["state_dict"]
    if not isinstance(state_dict, dict):
        raise RuntimeError(f"State artifact does not contain a valid state_dict: {path}")
    metadata = {key: value for key, value in payload.items() if key != "state_dict"}
    return state_dict, metadata


def load_labels(metadata: dict[str, Any]) -> list[str]:
    labels_path = try_find_input_file(LABELS_FILE_NAME)
    if labels_path is not None:
        labels = [line.strip() for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if labels:
            return labels

    metadata_labels = metadata.get("labels")
    if isinstance(metadata_labels, list):
        labels = [str(item).strip() for item in metadata_labels if str(item).strip()]
        if labels:
            return labels

    raise RuntimeError("No labels were found in labels.txt or the state artifact metadata.")


def load_training_result() -> dict[str, Any]:
    result_path = try_find_input_file("training-result.json")
    if result_path is None:
        return {}
    return json.loads(result_path.read_text(encoding="utf-8"))


def build_mlp_model(input_features: int, hidden_sizes: list[int], label_count: int) -> tf.keras.Model:
    inputs = tf.keras.Input(shape=(input_features,), dtype=tf.float32, name="input_features")
    current = inputs
    dense_layers: list[tf.keras.layers.Layer] = []

    for index, units in enumerate(hidden_sizes, start=1):
        layer = tf.keras.layers.Dense(units, activation="relu", name=f"dense_{index}")
        current = layer(current)
        dense_layers.append(layer)

    output_layer = tf.keras.layers.Dense(label_count, activation=None, name="logits")
    outputs = output_layer(current)
    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="kws_mlp")
    model(np.zeros((1, input_features), dtype=np.float32))
    model._dense_layers = dense_layers + [output_layer]  # type: ignore[attr-defined]
    return model


def assign_mlp_weights(model: tf.keras.Model, state_dict: dict[str, torch.Tensor], hidden_sizes: list[int]) -> None:
    linear_key_pairs = []
    linear_indices = list(range(0, (len(hidden_sizes) + 1) * 2, 2))
    for index in linear_indices:
        linear_key_pairs.append((f"network.{index}.weight", f"network.{index}.bias"))

    dense_layers = getattr(model, "_dense_layers")
    if len(dense_layers) != len(linear_key_pairs):
        raise RuntimeError("Dense layer count does not match the PyTorch model state.")

    for keras_layer, (weight_key, bias_key) in zip(dense_layers, linear_key_pairs):
        if weight_key not in state_dict or bias_key not in state_dict:
            raise RuntimeError(f"Missing weight pair {weight_key} / {bias_key} in the state artifact.")
        weight = state_dict[weight_key].detach().cpu().numpy().astype(np.float32).T
        bias = state_dict[bias_key].detach().cpu().numpy().astype(np.float32)
        keras_layer.set_weights([weight, bias])


def build_ds_cnn_model(input_features: int, feature_shape: list[int], stem_channels: int, block_count: int, label_count: int) -> tf.keras.Model:
    inputs = tf.keras.Input(shape=(input_features,), dtype=tf.float32, name="input_features")
    current = tf.keras.layers.Reshape((feature_shape[0], feature_shape[1], 1), name="reshape_input")(inputs)
    current = tf.keras.layers.Conv2D(
        filters=stem_channels,
        kernel_size=(5, 3),
        strides=(1, 1),
        padding="same",
        use_bias=False,
        name="stem_conv",
    )(current)
    current = tf.keras.layers.BatchNormalization(name="stem_bn")(current)
    current = tf.keras.layers.ReLU(name="stem_relu")(current)

    for index in range(block_count):
        prefix = f"ds_{index}"
        current = tf.keras.layers.DepthwiseConv2D(
            kernel_size=(3, 3),
            strides=(1, 1),
            padding="same",
            use_bias=False,
            name=f"{prefix}_depthwise",
        )(current)
        current = tf.keras.layers.BatchNormalization(name=f"{prefix}_depthwise_bn")(current)
        current = tf.keras.layers.ReLU(name=f"{prefix}_depthwise_relu")(current)
        current = tf.keras.layers.Conv2D(
            filters=stem_channels,
            kernel_size=(1, 1),
            strides=(1, 1),
            padding="same",
            use_bias=False,
            name=f"{prefix}_pointwise",
        )(current)
        current = tf.keras.layers.BatchNormalization(name=f"{prefix}_pointwise_bn")(current)
        current = tf.keras.layers.ReLU(name=f"{prefix}_pointwise_relu")(current)

    current = tf.keras.layers.GlobalAveragePooling2D(name="avg_pool")(current)
    outputs = tf.keras.layers.Dense(label_count, activation=None, name="classifier")(current)
    model = tf.keras.Model(inputs=inputs, outputs=outputs, name="kws_ds_cnn")
    model(np.zeros((1, input_features), dtype=np.float32))
    return model


def assign_batch_norm(layer: tf.keras.layers.BatchNormalization, state_dict: dict[str, torch.Tensor], prefix: str) -> None:
    gamma = state_dict[f"{prefix}.weight"].detach().cpu().numpy().astype(np.float32)
    beta = state_dict[f"{prefix}.bias"].detach().cpu().numpy().astype(np.float32)
    moving_mean = state_dict[f"{prefix}.running_mean"].detach().cpu().numpy().astype(np.float32)
    moving_variance = state_dict[f"{prefix}.running_var"].detach().cpu().numpy().astype(np.float32)
    layer.set_weights([gamma, beta, moving_mean, moving_variance])


def assign_conv2d(layer: tf.keras.layers.Conv2D, weight: torch.Tensor) -> None:
    kernel = weight.detach().cpu().numpy().astype(np.float32)
    kernel = np.transpose(kernel, (2, 3, 1, 0))
    layer.set_weights([kernel])


def assign_depthwise_conv2d(layer: tf.keras.layers.DepthwiseConv2D, weight: torch.Tensor) -> None:
    kernel = weight.detach().cpu().numpy().astype(np.float32)
    kernel = np.transpose(kernel, (2, 3, 0, 1))
    layer.set_weights([kernel])


def assign_dense(layer: tf.keras.layers.Dense, weight: torch.Tensor, bias: torch.Tensor) -> None:
    kernel = weight.detach().cpu().numpy().astype(np.float32).T
    bias_values = bias.detach().cpu().numpy().astype(np.float32)
    layer.set_weights([kernel, bias_values])


def assign_ds_cnn_weights(model: tf.keras.Model, state_dict: dict[str, torch.Tensor], block_count: int) -> None:
    assign_conv2d(model.get_layer("stem_conv"), state_dict["stem_conv.weight"])
    assign_batch_norm(model.get_layer("stem_bn"), state_dict, "stem_bn")
    for index in range(block_count):
        prefix = f"blocks.{index}"
        assign_depthwise_conv2d(model.get_layer(f"ds_{index}_depthwise"), state_dict[f"{prefix}.depthwise.weight"])
        assign_batch_norm(model.get_layer(f"ds_{index}_depthwise_bn"), state_dict, f"{prefix}.depthwise_bn")
        assign_conv2d(model.get_layer(f"ds_{index}_pointwise"), state_dict[f"{prefix}.pointwise.weight"])
        assign_batch_norm(model.get_layer(f"ds_{index}_pointwise_bn"), state_dict, f"{prefix}.pointwise_bn")
    assign_dense(model.get_layer("classifier"), state_dict["classifier.weight"], state_dict["classifier.bias"])


def convert_to_tflite(model: tf.keras.Model) -> bytes:
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    return converter.convert()


def make_package_name(labels: list[str]) -> str:
    if PACKAGE_NAME_OVERRIDE:
        return PACKAGE_NAME_OVERRIDE
    command_labels = [label for label in labels if label not in SPECIAL_LABELS]
    base_name = slugify("-".join(command_labels[:4]) or "kws-model")
    return f"{base_name}-model.zip"


def package_display_name(labels: list[str]) -> str:
    if PACKAGE_DISPLAY_NAME:
        return PACKAGE_DISPLAY_NAME
    return ", ".join(label for label in labels if label not in SPECIAL_LABELS)


def write_package_zip(package_path: Path, model_path: Path, labels_path: Path, package_info_path: Path) -> None:
    staging_root = OUTPUT_DIR / ".package-staging"
    if staging_root.exists():
        for path in sorted(staging_root.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            else:
                path.rmdir()
        staging_root.rmdir()

    staging_root.mkdir(parents=True, exist_ok=True)
    (staging_root / "install.sh").write_text(INSTALL_SCRIPT, encoding="utf-8", newline="\n")
    models_dir = staging_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / MODEL_FILE_NAME).write_bytes(model_path.read_bytes())
    (models_dir / LABELS_FILE_NAME).write_bytes(labels_path.read_bytes())

    package_info = json.loads(package_info_path.read_text(encoding="utf-8"))
    package_info["package_name"] = package_path.name
    (models_dir / PACKAGE_INFO_FILE_NAME).write_text(json.dumps(package_info, indent=2) + "\n", encoding="utf-8")

    with zipfile.ZipFile(package_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(staging_root / "install.sh", arcname="install.sh")
        archive.write(models_dir / MODEL_FILE_NAME, arcname=f"models/{MODEL_FILE_NAME}")
        archive.write(models_dir / LABELS_FILE_NAME, arcname=f"models/{LABELS_FILE_NAME}")
        archive.write(models_dir / PACKAGE_INFO_FILE_NAME, arcname=f"models/{PACKAGE_INFO_FILE_NAME}")

    for path in sorted(staging_root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        else:
            path.rmdir()
    staging_root.rmdir()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    state_path = find_input_file(WEIGHTS_NAME)
    state_dict, metadata = load_state_artifact(state_path)
    labels = load_labels(metadata)
    training_result = load_training_result()

    architecture = str(metadata.get("model_architecture", "")).strip().lower()
    if not architecture:
        architecture = str(training_result.get("model_architecture", "mlp")).strip().lower() or "mlp"

    if architecture == DEFAULT_DSCNN_ARCHITECTURE:
        input_features = int(metadata.get("input_features", 490))
        feature_shape = [int(value) for value in metadata.get("feature_shape", [49, 10])]
        stem_channels = int(metadata.get("stem_channels", 64))
        block_count = int(metadata.get("block_count", 4))
        keras_model = build_ds_cnn_model(input_features, feature_shape, stem_channels, block_count, len(labels))
        assign_ds_cnn_weights(keras_model, state_dict, block_count)
        model_details = {
            "input_features": input_features,
            "feature_shape": feature_shape,
            "stem_channels": stem_channels,
            "block_count": block_count,
            "model_architecture": architecture,
        }
    else:
        input_features = int(metadata.get("input_features", 490))
        hidden_sizes = [int(value) for value in metadata.get("hidden_sizes", [128, 64])]
        keras_model = build_mlp_model(input_features, hidden_sizes, len(labels))
        assign_mlp_weights(keras_model, state_dict, hidden_sizes)
        model_details = {
            "input_features": input_features,
            "hidden_sizes": hidden_sizes,
            "model_architecture": architecture or "mlp",
        }

    tflite_bytes = convert_to_tflite(keras_model)

    model_path = OUTPUT_DIR / MODEL_FILE_NAME
    labels_path = OUTPUT_DIR / LABELS_FILE_NAME
    package_info_path = OUTPUT_DIR / PACKAGE_INFO_FILE_NAME
    result_path = OUTPUT_DIR / CONVERSION_RESULT_FILE_NAME
    package_path = OUTPUT_DIR / make_package_name(labels)

    model_path.write_bytes(tflite_bytes)
    labels_path.write_text("\n".join(labels) + "\n", encoding="utf-8")
    package_info = {
        "package_name": package_path.name,
        "display_name": package_display_name(labels),
        "installed_model_name": MODEL_FILE_NAME,
        "labels_file": LABELS_FILE_NAME,
        "model_architecture": model_details["model_architecture"],
    }
    package_info_path.write_text(json.dumps(package_info, indent=2) + "\n", encoding="utf-8")
    write_package_zip(package_path, model_path, labels_path, package_info_path)

    result = {
        "input_state_path": str(state_path),
        "label_count": len(labels),
        "labels": labels,
        "model_file": MODEL_FILE_NAME,
        "labels_file": LABELS_FILE_NAME,
        "package_info_file": PACKAGE_INFO_FILE_NAME,
        "package_file": package_path.name,
        "training_result": training_result,
        **model_details,
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {model_path}", flush=True)
    print(f"Wrote {labels_path}", flush=True)
    print(f"Wrote {package_info_path}", flush=True)
    print(f"Wrote {package_path}", flush=True)
    print(f"Wrote {result_path}", flush=True)


if __name__ == "__main__":
    main()
