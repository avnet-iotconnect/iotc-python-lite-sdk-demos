# /IOTCONNECT Templates and Dashboard Exports (Shared Across Tracks)

This folder contains the cloud artifacts used by all three workshop tracks.

## Folder Contents

- `microchip-polarfire-tinyml-template.json`
  - Device template for all workshop devices.
  - Template name in `/IOTCONNECT`: `Microchip Polarfire ML`.
- `mchp-track1-dashboard-template.json`
  - Track 1 dashboard import (uses Track 1 waveform images).
- `mchp-track2-dashboard-template.json`
  - Track 2 dashboard import (uses Track 2 waveform images).
- `mchp-track3-dashboard-template.json`
  - Track 3 dashboard import (uses Track 3 waveform images).

## Import Order (Recommended)

1. Import `microchip-polarfire-tinyml-template.json` first.
2. Create or update workshop device(s) using template `Microchip Polarfire ML`.
3. Import the track-matched dashboard export JSON (optional but recommended).

## Command Contract Included in Template

- `classify`
- `bench`
- `status`
- `led`
- `leds`
- `load`
- `file-download`

## Notes

- The same device template is used for all tracks.
- Use a different dashboard template per track to map the correct waveform image set.

## /IOTCONNECT Documentation

- Device template management:
  - https://docs.iotconnect.io/iotconnect/user-manuals/devices/device/template-management/
- Dashboard import capability reference:
  - https://docs.iotconnect.io/iotconnect/platform/product-updates/aws/v1-0-8/
