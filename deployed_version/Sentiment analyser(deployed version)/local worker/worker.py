
import json
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

BUCKET = "sentiment-data-127228002846-ap-southeast-2-an"
PREFIX = "raw/run_id="
PROFILE = "sentiment-worker"
REGION = "ap-southeast-2"

STATE_FILE = Path(__file__).with_name("processed_datasets.json")


def load_processed():
    if not STATE_FILE.exists():
        return set()

    with STATE_FILE.open("r", encoding="utf-8") as f:
        return set(json.load(f))


def save_processed(processed):
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(sorted(processed), f, indent=2)


def main():
    session = boto3.Session(
        profile_name=PROFILE,
        region_name=REGION,
    )
    s3 = session.client("s3")
    processed = load_processed()

    paginator = s3.get_paginator("list_objects_v2")
    new_datasets = []

    try:
        for page in paginator.paginate(
            Bucket=BUCKET,
            Prefix=PREFIX,
        ):
            for obj in page.get("Contents", []):
                key = obj["Key"]

                if not key.endswith("/Checkpoint1.csv"):
                    continue

                if key not in processed:
                    new_datasets.append(key)

    except ClientError as exc:
        print(f"AWS error: {exc}")
        return

    if not new_datasets:
        print("No new datasets found.")
        return

    print(f"Found {len(new_datasets)} new dataset(s):")
    for key in sorted(new_datasets):
        print(f"  s3://{BUCKET}/{key}")

    print("\nDetection only: no datasets downloaded or processed.")
    print("No completion records have been changed.")


if __name__ == "__main__":
    main()
