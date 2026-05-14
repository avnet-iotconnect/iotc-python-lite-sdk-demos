#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

tar -czf package.tar.gz -C ./src .
echo "Package created: $(pwd)/package.tar.gz"
echo "Files included:"
tar -tzf package.tar.gz
