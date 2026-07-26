# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# -----------------------------------------------------------------------------
# Persistent VLM worker.
#
# The NXP `vlm` module is single-shot: each `python3 -m vlm ... -q <question>`
# loads the ~250 MB SmolVLM model (~40 s) before it can answer. This worker
# loads the model ONCE, then answers many (image, question) requests read as
# JSON lines from stdin - so ask-vlm only pays the load on the first call and
# subsequent questions answer in ~5 s. Driven by PersistentVLM in app.py.
#
# Protocol:
#   stdout "VLM_READY" once the model is loaded.
#   per request (one JSON line in: {"image": <path>, "question": <text>}):
#     VLM_ANSWER_BEGIN / <answer> / VLM_ANSWER_END / <vlm.str_perf() line> / VLM_DONE
# -----------------------------------------------------------------------------
import json
import sys

from vlm.modeling_vlm import make_VLM
from vlm.user_config import Config as user_params
from transformers.image_utils import load_image


def main():
    model, precision, init_image = sys.argv[1], sys.argv[2], sys.argv[3]
    vlm = make_VLM(model, precision, user_params=user_params, fixed_image=init_image)
    vlm.image_features = vlm.run_vision(vlm.image_inputs)  # prime the first frame
    print("VLM_READY", flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        frame = req.get("image")
        question = req.get("question") or "Describe what you see in this image."
        try:
            # Swap in the fresh camera frame and force a re-encode of the new
            # image (the model + processor stay loaded - that's the warm part).
            vlm.image = load_image(frame)
            vlm.image_inputs = vlm.processor.image_processor(
                [[vlm.image]], return_row_col_info=True, return_tensors="np")
            vlm.image_features = None
            answer = "".join(t for t in vlm.process_message(question)).strip()
            perf = vlm.str_perf()
        except Exception as e:  # keep the worker alive across a bad request
            answer, perf = "", "ERROR: %s" % e
        print("VLM_ANSWER_BEGIN", flush=True)
        print(answer, flush=True)
        print("VLM_ANSWER_END", flush=True)
        print(perf, flush=True)
        print("VLM_DONE", flush=True)


if __name__ == "__main__":
    main()
