from __future__ import annotations

import torch
from torch import nn

SPECTROGRAM_LENGTH = 49
DCT_COEFFICIENT_COUNT = 10
INPUT_FEATURES = SPECTROGRAM_LENGTH * DCT_COEFFICIENT_COUNT
HIDDEN_SIZES = (128, 64)


class KeywordSpotter(nn.Module):
    def __init__(self, num_labels: int):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(INPUT_FEATURES, HIDDEN_SIZES[0]),
            nn.ReLU(inplace=True),
            nn.Linear(HIDDEN_SIZES[0], HIDDEN_SIZES[1]),
            nn.ReLU(inplace=True),
            nn.Linear(HIDDEN_SIZES[1], num_labels),
        )

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        if inputs.ndim > 2:
            inputs = torch.flatten(inputs, start_dim=1)
        return self.network(inputs)


def example_input() -> torch.Tensor:
    return torch.zeros((1, INPUT_FEATURES), dtype=torch.float32)
