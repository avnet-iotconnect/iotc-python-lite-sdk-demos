#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
# Authors: Michael Lamp <michael@lamptribe.com> et al.
#
# Installs the /IOTCONNECT side of the eIQ GenAI Flow Edge LLM demo.
# NXP's eIQ GenAI Flow demonstrator itself is installed separately -- see README.md.

export PIP_ROOT_USER_ACTION=ignore  # Suppresses venv warning

python3 -m pip install iotconnect-sdk-lite requests

GENAI_DIR="${GENAI_DIR:-/root/eiq_genai_flow}"

# Create the default demo configuration if one does not exist yet
if [ ! -f /opt/demo/genai-config.json ]; then
cat > /opt/demo/genai-config.json <<EOF
{
  "genai_dir": "$GENAI_DIR",
  "python": "python3",
  "model": "danube-500M-q8",
  "backend": "cpu",
  "output_silence_s": 5,
  "prompt_timeout_s": 600,
  "benchmark_timeout_s": 3600,
  "telemetry_interval_s": 10
}
EOF
echo "Created default /opt/demo/genai-config.json (genai_dir=$GENAI_DIR)"
fi

if [ -f "$GENAI_DIR/eiq_genai_flow.py" ]; then
    echo "Found eIQ GenAI Flow at $GENAI_DIR"
else
    echo "=========================================================================="
    echo "WARNING: eIQ GenAI Flow was not found at $GENAI_DIR"
    echo "The ask-llm and run-benchmark commands will fail until it is installed."
    echo "Follow the 'Install NXP eIQ GenAI Flow' section of the demo README:"
    echo "https://github.com/nxp-appcodehub/dm-eiq-genai-flow-demonstrator"
    echo "If you installed it somewhere else, edit genai_dir in /opt/demo/genai-config.json"
    echo "=========================================================================="
fi

echo "Installation complete!"
