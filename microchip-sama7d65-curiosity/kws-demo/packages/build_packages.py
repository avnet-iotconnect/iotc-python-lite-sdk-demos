#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path


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

MODEL_PACKAGES = [
    {
        "archive_name": "model-ds-cnn-small-int8.zip",
        "display_name": "DS-CNN Small INT8",
        "source": "local",
        "source_path": "src/models/ds_cnn_s_quantized.tflite",
        "source_url": "https://media.githubusercontent.com/media/Arm-Examples/ML-zoo/master/models/keyword_spotting/ds_cnn_small/model_package_tf/model_archive/TFLite/tflite_int8/ds_cnn_s_quantized.tflite",
        "upstream_filename": "ds_cnn_s_quantized.tflite",
        "accuracy": "93.11%",
    },
    {
        "archive_name": "model-ds-cnn-small-fp32.zip",
        "display_name": "DS-CNN Small FP32",
        "source": "remote",
        "source_url": "https://media.githubusercontent.com/media/Arm-Examples/ML-zoo/master/models/keyword_spotting/ds_cnn_small/model_package_tf/model_archive/TFLite/tflite_fp32/ds_cnn_s.tflite",
        "upstream_filename": "ds_cnn_s.tflite",
        "accuracy": "93.89%",
    },
    {
        "archive_name": "model-ds-cnn-medium-int8.zip",
        "display_name": "DS-CNN Medium INT8",
        "source": "remote",
        "source_url": "https://media.githubusercontent.com/media/Arm-Examples/ML-zoo/master/models/keyword_spotting/ds_cnn_medium/model_package_tf/model_archive/TFLite/tflite_int8/ds_cnn_m_quantized.tflite",
        "upstream_filename": "ds_cnn_m_quantized.tflite",
        "accuracy": "93.93%",
    },
    {
        "archive_name": "model-ds-cnn-medium-fp32.zip",
        "display_name": "DS-CNN Medium FP32",
        "source": "remote",
        "source_url": "https://media.githubusercontent.com/media/Arm-Examples/ML-zoo/master/models/keyword_spotting/ds_cnn_medium/model_package_tf/model_archive/TFLite/tflite_fp32/ds_cnn_m.tflite",
        "upstream_filename": "ds_cnn_m.tflite",
        "accuracy": "94.27%",
    },
    {
        "archive_name": "model-cnn-small-int8.zip",
        "display_name": "CNN Small INT8",
        "source": "remote",
        "source_url": "https://media.githubusercontent.com/media/Arm-Examples/ML-zoo/master/models/keyword_spotting/cnn_small/model_package_tf/model_archive/TFLite/tflite_int8/cnn_s_quantized.tflite",
        "upstream_filename": "cnn_s_quantized.tflite",
        "accuracy": "90.18%",
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_tree(archive: zipfile.ZipFile, source_dir: Path) -> None:
    for path in sorted(source_dir.rglob("*")):
        if path.is_dir():
            continue
        relative_path = path.relative_to(source_dir)
        if "__pycache__" in relative_path.parts or path.suffix == ".pyc":
            continue
        archive.write(path, arcname=str(relative_path).replace("\\", "/"))


def build_full_package(demo_root: Path, packages_dir: Path) -> dict:
    archive_path = packages_dir / "kws-demo-package.zip"
    src_dir = demo_root / "src"
    with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        add_tree(archive, src_dir)
    return {
        "name": archive_path.name,
        "type": "full-app",
        "sha256": sha256_file(archive_path),
        "size_bytes": archive_path.stat().st_size,
    }


def fetch_model(package_def: dict, demo_root: Path, cache_dir: Path) -> Path:
    if package_def["source"] == "local":
        return demo_root / package_def["source_path"]

    target_path = cache_dir / package_def["upstream_filename"]
    if target_path.exists():
        return target_path

    with urllib.request.urlopen(package_def["source_url"]) as response:
        target_path.write_bytes(response.read())
    return target_path


def build_model_package(package_def: dict, demo_root: Path, packages_dir: Path, cache_dir: Path) -> dict:
    archive_path = packages_dir / package_def["archive_name"]
    labels_path = demo_root / "src" / "models" / "labels.txt"
    model_source = fetch_model(package_def, demo_root, cache_dir)

    with tempfile.TemporaryDirectory(prefix="kws-model-package-") as temp_dir:
        staging_dir = Path(temp_dir)
        models_dir = staging_dir / "models"
        models_dir.mkdir(parents=True, exist_ok=True)

        normalized_install_script = INSTALL_SCRIPT.replace("\r\n", "\n").replace("\r", "\n")
        (staging_dir / "install.sh").write_text(normalized_install_script, encoding="utf-8", newline="\n")
        shutil.copyfile(model_source, models_dir / "model.tflite")
        shutil.copyfile(labels_path, models_dir / "labels.txt")
        (models_dir / "package-info.json").write_text(
            json.dumps(
                {
                    "package_name": package_def["archive_name"],
                    "display_name": package_def["display_name"],
                    "upstream_filename": package_def["upstream_filename"],
                    "source_url": package_def["source_url"],
                    "installed_model_name": "model.tflite",
                    "labels_file": "labels.txt",
                    "accuracy": package_def["accuracy"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            add_tree(archive, staging_dir)

    return {
        "name": archive_path.name,
        "type": "model-only",
        "display_name": package_def["display_name"],
        "source_url": package_def["source_url"],
        "accuracy": package_def["accuracy"],
        "sha256": sha256_file(archive_path),
        "size_bytes": archive_path.stat().st_size,
    }


def main() -> None:
    demo_root = Path(__file__).resolve().parents[1]
    packages_dir = Path(__file__).resolve().parent
    manifest = {
        "generated_from": str(demo_root),
        "packages": [],
    }

    with tempfile.TemporaryDirectory(prefix="kws-package-cache-") as temp_dir:
        cache_dir = Path(temp_dir)
        manifest["packages"].append(build_full_package(demo_root, packages_dir))
        for package_def in MODEL_PACKAGES:
            manifest["packages"].append(build_model_package(package_def, demo_root, packages_dir, cache_dir))

    manifest_path = packages_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {manifest_path}")
    for package_info in manifest["packages"]:
        print(f"Wrote {packages_dir / package_info['name']}")


if __name__ == "__main__":
    main()
