#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path
from typing import List


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a trained KWS model for the Microchip SAMA7D65 demo.")
    parser.add_argument("--tflite-path", required=True, help="Path to the converted TFLite model.")
    parser.add_argument("--output-dir", required=True, help="Directory to write model.tflite and labels.txt into.")
    parser.add_argument(
        "--wanted-words",
        default="",
        help="Comma-separated target commands. Used to generate labels.txt when --labels-file is not supplied.",
    )
    parser.add_argument(
        "--labels-file",
        default="",
        help="Optional file containing one label per line. When supplied, it overrides --wanted-words.",
    )
    parser.add_argument(
        "--package-path",
        default="",
        help="Optional .zip path to generate a ready-to-deploy model-only package.",
    )
    return parser.parse_args()


def load_labels(args: argparse.Namespace) -> List[str]:
    if args.labels_file:
        labels = [line.strip() for line in Path(args.labels_file).read_text(encoding="utf-8").splitlines() if line.strip()]
        if not labels:
            raise ValueError("labels file is empty")
        return labels

    wanted_words = [word.strip() for word in args.wanted_words.split(",") if word.strip()]
    if not wanted_words:
        raise ValueError("either --labels-file or --wanted-words must provide labels")
    return ["_silence_", "_unknown_", *wanted_words]


def write_output(tflite_path: Path, output_dir: Path, labels: List[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tflite_path, output_dir / "model.tflite")
    (output_dir / "labels.txt").write_text("\n".join(labels) + "\n", encoding="utf-8")
    (output_dir / "package-info.json").write_text(
        json.dumps(
            {
                "package_name": "",
                "display_name": output_dir.name,
                "installed_model_name": "model.tflite",
                "labels_file": "labels.txt",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "export-info.json").write_text(
        json.dumps(
            {
                "source_tflite": str(tflite_path.resolve()),
                "labels": labels,
                "output_model": "model.tflite",
                "output_labels": "labels.txt",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def create_package(output_dir: Path, package_path: Path) -> None:
    package_path.parent.mkdir(parents=True, exist_ok=True)
    staging_root = output_dir.parent / f".{output_dir.name}-package"
    if staging_root.exists():
        shutil.rmtree(staging_root)
    staging_root.mkdir(parents=True)

    normalized_install_script = INSTALL_SCRIPT.replace("\r\n", "\n").replace("\r", "\n")
    (staging_root / "install.sh").write_text(normalized_install_script, encoding="utf-8", newline="\n")
    models_dir = staging_root / "models"
    models_dir.mkdir()
    shutil.copyfile(output_dir / "model.tflite", models_dir / "model.tflite")
    shutil.copyfile(output_dir / "labels.txt", models_dir / "labels.txt")
    package_info = json.loads((output_dir / "package-info.json").read_text(encoding="utf-8"))
    package_info["package_name"] = package_path.name
    (models_dir / "package-info.json").write_text(json.dumps(package_info, indent=2) + "\n", encoding="utf-8")

    with zipfile.ZipFile(package_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(staging_root / "install.sh", arcname="install.sh")
        archive.write(models_dir / "model.tflite", arcname="models/model.tflite")
        archive.write(models_dir / "labels.txt", arcname="models/labels.txt")
        archive.write(models_dir / "package-info.json", arcname="models/package-info.json")

    shutil.rmtree(staging_root)


def main() -> None:
    args = parse_args()
    tflite_path = Path(args.tflite_path).resolve()
    if not tflite_path.is_file():
        raise FileNotFoundError(f"TFLite model not found: {tflite_path}")

    output_dir = Path(args.output_dir).resolve()
    labels = load_labels(args)
    write_output(tflite_path, output_dir, labels)

    if args.package_path:
        create_package(output_dir, Path(args.package_path).resolve())

    print(f"Wrote {output_dir / 'model.tflite'}")
    print(f"Wrote {output_dir / 'labels.txt'}")
    if args.package_path:
        print(f"Wrote {Path(args.package_path).resolve()}")


if __name__ == "__main__":
    main()
