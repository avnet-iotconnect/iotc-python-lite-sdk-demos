# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, UTC

import boto3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit the KWS SageMaker training job.")
    parser.add_argument("--region", default=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1")
    parser.add_argument("--role-arn", default=os.getenv("KWS_SAGEMAKER_ROLE_ARN", ""))
    parser.add_argument("--image-uri", default=os.getenv("KWS_SAGEMAKER_IMAGE_URI", ""))
    parser.add_argument("--dataset-s3-uri", required=True)
    parser.add_argument("--manifest-s3-uri", default=os.getenv("KWS_MANIFEST_S3_URI", ""))
    parser.add_argument("--output-bucket", default=os.getenv("KWS_TRAINING_OUTPUT_BUCKET", ""))
    parser.add_argument("--output-prefix", default=os.getenv("KWS_TRAINING_OUTPUT_PREFIX", "kws-training/output"))
    parser.add_argument("--weights-prefix", default=os.getenv("KWS_SAGEMAKER_WEIGHTS_PREFIX", "kws-training/weights"))
    parser.add_argument("--instance-type", default=os.getenv("KWS_SAGEMAKER_INSTANCE_TYPE", "ml.m5.xlarge"))
    parser.add_argument("--instance-count", type=int, default=int(os.getenv("KWS_SAGEMAKER_INSTANCE_COUNT", "1")))
    parser.add_argument("--max-runtime-secs", type=int, default=int(os.getenv("KWS_SAGEMAKER_MAX_RUNTIME_SECS", "14400")))
    parser.add_argument("--epochs", type=int, default=int(os.getenv("KWS_SAGEMAKER_TRAIN_EPOCHS", "20")))
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("KWS_SAGEMAKER_TRAIN_BATCH_SIZE", "16")))
    parser.add_argument("--learning-rate", type=float, default=float(os.getenv("KWS_SAGEMAKER_TRAIN_LEARNING_RATE", "0.001")))
    parser.add_argument("--job-name-prefix", default="kws-train")
    parser.add_argument("--wanted-words", default=os.getenv("KWS_WANTED_WORDS", ""))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def join_s3(bucket: str, *parts: str) -> str:
    clean = [part.strip("/") for part in parts if part and part.strip("/")]
    return f"s3://{bucket}/{'/'.join(clean)}"


def main():
    args = parse_args()
    if not args.role_arn:
        raise SystemExit("Missing --role-arn or KWS_SAGEMAKER_ROLE_ARN")
    if not args.image_uri:
        raise SystemExit("Missing --image-uri or KWS_SAGEMAKER_IMAGE_URI")
    if not args.output_bucket:
        raise SystemExit("Missing --output-bucket or KWS_TRAINING_OUTPUT_BUCKET")

    job_name = f"{args.job_name_prefix}-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    output_uri = join_s3(args.output_bucket, args.output_prefix, job_name)
    weights_uri = join_s3(args.output_bucket, args.weights_prefix, job_name, "model.pt")
    state_uri = join_s3(args.output_bucket, args.weights_prefix, job_name, "model-state.pt")
    labels_uri = join_s3(args.output_bucket, args.weights_prefix, job_name, "labels.txt")
    results_uri = join_s3(args.output_bucket, args.weights_prefix, job_name, "training-result.json")

    request = {
        "TrainingJobName": job_name,
        "RoleArn": args.role_arn,
        "AlgorithmSpecification": {
            "TrainingImage": args.image_uri,
            "TrainingInputMode": "File",
        },
        "InputDataConfig": [
            {
                "ChannelName": "training",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": args.dataset_s3_uri,
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
                "ContentType": "application/gzip",
            }
        ],
        "OutputDataConfig": {"S3OutputPath": output_uri},
        "ResourceConfig": {
            "InstanceType": args.instance_type,
            "InstanceCount": args.instance_count,
            "VolumeSizeInGB": 30,
        },
        "StoppingCondition": {"MaxRuntimeInSeconds": args.max_runtime_secs},
        "Environment": {
            "KWS_MANIFEST_S3_URI": args.manifest_s3_uri,
            "KWS_WEIGHTS_UPLOAD_S3_URI": weights_uri,
            "KWS_STATE_UPLOAD_S3_URI": state_uri,
            "KWS_LABELS_UPLOAD_S3_URI": labels_uri,
            "KWS_RESULTS_UPLOAD_S3_URI": results_uri,
            "KWS_WANTED_WORDS": args.wanted_words,
            "KWS_TRAIN_EPOCHS": str(args.epochs),
            "KWS_TRAIN_BATCH_SIZE": str(args.batch_size),
            "KWS_TRAIN_LEARNING_RATE": str(args.learning_rate),
        },
        "HyperParameters": {
            "epochs": str(args.epochs),
            "batch-size": str(args.batch_size),
            "learning-rate": str(args.learning_rate),
            "wanted-words": args.wanted_words,
        },
    }

    if args.dry_run:
        print(json.dumps(request, indent=2))
        return

    session = boto3.session.Session(region_name=args.region)
    client = session.client("sagemaker")
    response = client.create_training_job(**request)
    print(
        json.dumps(
            {
                "training_job_name": job_name,
                "training_job_arn": response.get("TrainingJobArn", ""),
                "output_s3_uri": output_uri,
                "weights_s3_uri": weights_uri,
                "state_s3_uri": state_uri,
                "labels_s3_uri": labels_uri,
                "results_s3_uri": results_uri,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
