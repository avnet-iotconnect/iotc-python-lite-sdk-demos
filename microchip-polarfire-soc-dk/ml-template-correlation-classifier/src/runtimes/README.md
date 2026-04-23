# Runtime Binaries

Prebuilt Tiny-ML binaries are downloaded from S3 by `create-package.sh` if not present locally:

- [invert_and_threshold.no_accel.elf](https://s3.us-east-1.amazonaws.com/avnetpublicaccess/large-repo-files/invert_and_threshold.no_accel.elf)
- [invert_and_threshold.accel.elf](https://s3.us-east-1.amazonaws.com/avnetpublicaccess/large-repo-files/invert_and_threshold.accel.elf)

These are produced by SmartHLS. Quickstart flow does not require SmartHLS if the binaries are already included in the package.
