# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
from __future__ import annotations

import torch
from torch import nn

SPECTROGRAM_LENGTH = 49
DCT_COEFFICIENT_COUNT = 10
INPUT_FEATURES = SPECTROGRAM_LENGTH * DCT_COEFFICIENT_COUNT
FEATURE_SHAPE = (SPECTROGRAM_LENGTH, DCT_COEFFICIENT_COUNT)
MODEL_ARCHITECTURE = "ds-cnn-mfcc"
STEM_CHANNELS = 64
BLOCK_COUNT = 4
DROPOUT_RATE = 0.20


class DepthwiseSeparableBlock(nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        self.depthwise = nn.Conv2d(
            channels,
            channels,
            kernel_size=(3, 3),
            stride=(1, 1),
            padding=(1, 1),
            groups=channels,
            bias=False,
        )
        self.depthwise_bn = nn.BatchNorm2d(channels)
        self.depthwise_relu = nn.ReLU(inplace=True)
        self.pointwise = nn.Conv2d(channels, channels, kernel_size=(1, 1), bias=False)
        self.pointwise_bn = nn.BatchNorm2d(channels)
        self.pointwise_relu = nn.ReLU(inplace=True)
        self.dropout = nn.Dropout(DROPOUT_RATE)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        current = self.depthwise(inputs)
        current = self.depthwise_bn(current)
        current = self.depthwise_relu(current)
        current = self.pointwise(current)
        current = self.pointwise_bn(current)
        current = self.pointwise_relu(current)
        return self.dropout(current)


class KeywordSpotter(nn.Module):
    def __init__(self, num_labels: int):
        super().__init__()
        self.stem_conv = nn.Conv2d(
            in_channels=1,
            out_channels=STEM_CHANNELS,
            kernel_size=(5, 3),
            stride=(1, 1),
            padding=(2, 1),
            bias=False,
        )
        self.stem_bn = nn.BatchNorm2d(STEM_CHANNELS)
        self.stem_relu = nn.ReLU(inplace=True)
        self.stem_dropout = nn.Dropout(DROPOUT_RATE)
        self.blocks = nn.ModuleList([DepthwiseSeparableBlock(STEM_CHANNELS) for _ in range(BLOCK_COUNT)])
        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.classifier = nn.Linear(STEM_CHANNELS, num_labels)

    def _reshape_inputs(self, inputs: torch.Tensor) -> torch.Tensor:
        if inputs.ndim == 2:
            if inputs.shape[1] != INPUT_FEATURES:
                raise RuntimeError(f"Expected {INPUT_FEATURES} features, found {inputs.shape[1]}")
            return inputs.reshape(-1, 1, SPECTROGRAM_LENGTH, DCT_COEFFICIENT_COUNT)
        if inputs.ndim == 3:
            if tuple(inputs.shape[1:]) != FEATURE_SHAPE:
                raise RuntimeError(f"Expected feature shape {FEATURE_SHAPE}, found {tuple(inputs.shape[1:])}")
            return inputs.unsqueeze(1)
        if inputs.ndim == 4:
            if inputs.shape[1] == 1:
                return inputs
            if inputs.shape[-1] == 1:
                return inputs.permute(0, 3, 1, 2)
        raise RuntimeError(f"Unsupported input shape: {tuple(inputs.shape)}")

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        current = self._reshape_inputs(inputs)
        current = self.stem_conv(current)
        current = self.stem_bn(current)
        current = self.stem_relu(current)
        current = self.stem_dropout(current)
        for block in self.blocks:
            current = block(current)
        current = self.pool(current)
        current = torch.flatten(current, start_dim=1)
        return self.classifier(current)


def example_input() -> torch.Tensor:
    return torch.zeros((1, INPUT_FEATURES), dtype=torch.float32)
