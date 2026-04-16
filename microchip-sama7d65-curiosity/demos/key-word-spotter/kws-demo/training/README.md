# KWS Training

This folder contains host-side assets for retraining the Microchip SAMA7D65 KWS demo with new command words.

The training flow is based on Arm's `ds_cnn_small` model package from `Arm-Examples/ML-zoo`. The exported artifacts from this folder are shaped for the demo runtime in `../src/`:

- `16 kHz` mono audio
- `1 second` clips
- `40 ms` window
- `20 ms` stride
- `10` MFCC coefficients
- output files: `model.tflite`, `labels.txt`, and `package-info.json`

## 1. Dataset Layout

Use [dataset-layout/README.md](./dataset-layout/README.md) as the on-disk layout reference. The minimal rule is:

- one folder per spoken label
- one `wav` file per utterance
- all clips normalized to `16 kHz`, mono, roughly `1 second`
- `_background_noise_` contains long background recordings for augmentation
- any folder not listed in `--wanted_words` becomes part of `_unknown_`

## 2. Set Up the Training Environment

Arm's model package documents Python `3.7` as the baseline. WSL2 Ubuntu is the simplest path on Windows.

Clone the upstream training package:

```bash
git clone https://github.com/Arm-Examples/ML-zoo.git
cd ML-zoo/models/keyword_spotting/ds_cnn_small/model_package_tf
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 3. Train

Edit the variables at the top of [train-ds-cnn-small.sh](./train-ds-cnn-small.sh), then run:

```bash
bash ./train-ds-cnn-small.sh
```

That script keeps the frontend aligned with the board demo and writes checkpoints under `work/DS_CNN/DS_CNN_S/training/best/`.

## 4. Convert to TFLite

Pick the best checkpoint and convert it with Arm's upstream script.

Int8:

```bash
python convert_to_tflite.py \
  --data_url= \
  --data_dir /path/to/your/dataset \
  --wanted_words lights,fan,heat \
  --sample_rate 16000 \
  --clip_duration_ms 1000 \
  --window_size_ms 40 \
  --window_stride_ms 20 \
  --dct_coefficient_count 10 \
  --model_architecture ds_cnn \
  --model_size_info 5 64 10 4 2 2 64 3 3 1 1 64 3 3 1 1 64 3 3 1 1 64 3 3 1 1 \
  --checkpoint /path/to/best/ds_cnn_<score>_ckpt \
  --inference_type int8
```

Fp32:

```bash
python convert_to_tflite.py \
  --data_url= \
  --data_dir /path/to/your/dataset \
  --wanted_words lights,fan,heat \
  --sample_rate 16000 \
  --clip_duration_ms 1000 \
  --window_size_ms 40 \
  --window_stride_ms 20 \
  --dct_coefficient_count 10 \
  --model_architecture ds_cnn \
  --model_size_info 5 64 10 4 2 2 64 3 3 1 1 64 3 3 1 1 64 3 3 1 1 64 3 3 1 1 \
  --checkpoint /path/to/best/ds_cnn_<score>_ckpt \
  --no-quantize
```

## 5. Export for This Demo

Use [export_for_demo.py](./export_for_demo.py) to emit the exact files this demo loads:

```bash
python export_for_demo.py \
  --tflite-path ./ds_cnn_quantized.tflite \
  --wanted-words lights,fan,heat \
  --output-dir ./out/lights-fan-heat \
  --package-path ./out/lights-fan-heat-model.zip
```

That produces:

- `out/lights-fan-heat/model.tflite`
- `out/lights-fan-heat/labels.txt`
- `out/lights-fan-heat/package-info.json`
- `out/lights-fan-heat-model.zip` if `--package-path` is provided

The generated `.zip` is ready for:

- `/IOTCONNECT` OTA
- the `file-download` command
- manual copy to the board followed by `python3 -m zipfile -e ... . && bash ./install.sh`

## 6. Deploy a Custom Model

Manual copy:

```bash
scp ./out/lights-fan-heat-model.zip root@<board-ip>:/opt/demo/
ssh root@<board-ip> 'cd /opt/demo && python3 -m zipfile -e lights-fan-heat-model.zip . && bash ./install.sh'
```

Or publish the generated `.zip` through `/IOTCONNECT` firmware/OTA.

## Notes

- Keep the frontend parameters unchanged unless you also update `../src/kws_engine.py`.
- The runtime supports `fp32`, `int8`, and `uint8` TFLite inputs. It does not support `int16` models.
- `labels.txt` must match the model output order exactly.
- `package-info.json` lets the runtime report `model_package` and distinguish one installed model package from another.
