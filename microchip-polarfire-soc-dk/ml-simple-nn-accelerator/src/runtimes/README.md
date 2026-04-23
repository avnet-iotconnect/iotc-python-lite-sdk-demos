# Runtime ELFs (Required)

Prebuilt neural network runtime binaries are downloaded from S3 by `create-package.sh` if not present locally:

- [tinyml_nn.no_accel.elf](https://s3.us-east-1.amazonaws.com/avnetpublicaccess/large-repo-files/tinyml_nn.no_accel.elf) (software path)
- [tinyml_nn.accel.elf](https://s3.us-east-1.amazonaws.com/avnetpublicaccess/large-repo-files/tinyml_nn.accel.elf) (hardware-accelerated path)

These names are referenced by `src/ml_runner.py`.
