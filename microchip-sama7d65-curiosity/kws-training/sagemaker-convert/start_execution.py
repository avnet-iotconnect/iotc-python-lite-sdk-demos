from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, UTC
from urllib.parse import urlparse

import boto3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the IoTConnect Step Functions conversion pipeline.")
    parser.add_argument("--region", default=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1")
    parser.add_argument("--state-machine-arn", required=True)
    parser.add_argument("--processing-image-uri", required=True)
    parser.add_argument("--input-s3-uri", required=True, help="S3 prefix that contains model-state.pt and labels.txt")
    parser.add_argument("--weights-name", default="model-state.pt")
    parser.add_argument("--output-s3-uri", required=True)
    parser.add_argument("--project-name", default="kws-training")
    parser.add_argument("--instance-type", default="ml.m5.xlarge")
    parser.add_argument("--volume-size-gb", type=int, default=30)
    parser.add_argument("--execution-name-prefix", default="kws-convert")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def normalize_input_s3_uri(input_s3_uri: str, weights_name: str) -> tuple[str, str]:
    parsed = urlparse(input_s3_uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise SystemExit(f"Invalid S3 URI: {input_s3_uri}")

    object_path = parsed.path.lstrip("/")
    explicit_name = weights_name.strip()
    if explicit_name:
        return input_s3_uri.rstrip("/"), explicit_name

    if object_path.endswith("/"):
        return input_s3_uri.rstrip("/"), "model-state.pt"

    prefix, file_name = object_path.rsplit("/", 1)
    return f"s3://{parsed.netloc}/{prefix}", file_name


def main() -> None:
    args = parse_args()
    execution_name = f"{args.execution_name_prefix}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    input_s3_uri, weights_name = normalize_input_s3_uri(args.input_s3_uri, args.weights_name)
    payload = {
        "ProjectName": args.project_name,
        "ProcessingImageUri": args.processing_image_uri,
        "InstanceType": args.instance_type,
        "VolumeSizeGB": args.volume_size_gb,
        "WeightsName": weights_name,
        "InputS3Uri": input_s3_uri,
        "OutputS3Uri": args.output_s3_uri,
    }

    if args.dry_run:
        print(
            json.dumps(
                {
                    "execution_name": execution_name,
                    "state_machine_arn": args.state_machine_arn,
                    "input": payload,
                },
                indent=2,
            )
        )
        return

    session = boto3.session.Session(region_name=args.region)
    client = session.client("stepfunctions")
    response = client.start_execution(
        stateMachineArn=args.state_machine_arn,
        name=execution_name,
        input=json.dumps(payload),
    )
    print(
        json.dumps(
            {
                "execution_name": execution_name,
                "execution_arn": response["executionArn"],
                "state_machine_arn": args.state_machine_arn,
                "output_s3_uri": args.output_s3_uri,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
