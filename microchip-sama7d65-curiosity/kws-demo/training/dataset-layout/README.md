# Dataset Layout

Use this folder as a local template for your training dataset. Replace the placeholder command folders with your real command names.

Example layout:

```text
dataset-layout/
  _background_noise_/
    room-tone-01.wav
    hvac-01.wav
  lights/
    speaker1_001.wav
    speaker2_014.wav
  fan/
    speaker1_003.wav
  heat/
    speaker3_007.wav
  marvin/
    speaker4_011.wav
```

Notes:

- `_background_noise_` is special and should contain longer background recordings.
- `lights`, `fan`, and `heat` are example target commands.
- `marvin` is an example non-target folder. If it is not in `--wanted_words`, it becomes part of `_unknown_`.
- Keep clips mono, `16 kHz`, and close to `1 second`.
- More speakers and more recording conditions matter more than squeezing the model.
