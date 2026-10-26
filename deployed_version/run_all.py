import argparse
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3
import pandas as pd
from botocore.exceptions import BotoCoreError, ClientError

# ---------------------------------------------------------------------------
# Verified Project & AWS Configuration
# ---------------------------------------------------------------------------
AWS_PROFILE = "sentiment-worker"
AWS_REGION = "ap-southeast-2"
S3_BUCKET = "sentiment-data-127228002846-ap-southeast-2-an"

ECS_CLUSTER = "scraper"
TASK_DEFINITION = "sentiment-scraper-task:3"
CONTAINER_NAME = "Main"

SUBNETS = [
    "subnet-084c6effc2a3ee8ee",
    "subnet-06583d5cd7935b17f",
    "subnet-0770d8708b8340b4f",
]
SECURITY_GROUPS = ["sg-082085345db4906d3"]

PROJECT_ROOT = Path(__file__).resolve().parent
ML_PYTHON_EXE = Path(r"C:\ai_env\Scripts\python.exe")
ML_PIPELINE_SCRIPT = PROJECT_ROOT / "ML_Pipeline" / "run_pipeline.py"

POLL_INTERVAL_SECONDS = 10

VALID_SOURCES = frozenset(
    {"youtube", "reddit", "googleplay", "steam", "1", "2", "3", "4", "yt", "google_play", "playstore"}
)

EXPECTED_CHECKPOINT2_COLUMNS = [
    "Unnamed: 0",
    "url",
    "author",
    "date",
    "source",
    "category",
    "parsed_date",
    "domain",
    "ID",
    "text",
    "Sentiment",
    "Rating",
]

EXPECTED_CHECKPOINT3_COLUMNS = [
    "Unnamed: 0",
    "url",
    "author",
    "date",
    "source",
    "category",
    "parsed_date",
    "domain",
    "ID",
    "text",
    "Sentiment",
    "Rating",
    "Local_Topic",
    "Local_Topic_Keywords",
    "Cluster_Confidence",
    "Topic_Diversity",
    "Local_Topic_Quality",
    "Global_Topic",
    "Global_Topic_Keywords",
    "Global_Topic_Quality",
    "Global_Cluster_Confidence",
    "Global_Topic_Diversity",
]


def fail(stage: str, message: str, exit_code: int = 1):
    print(f"\n[FAILED at Stage: {stage}] {message}", file=sys.stderr)
    sys.exit(exit_code)


def validate_inputs(targets: Optional[List[List[str]]], max_reviews: Optional[int]) -> None:
    """Validate user inputs before launching any cloud resources."""
    if max_reviews is not None and max_reviews <= 0:
        fail("Stage A - Argument Validation", f"--max-reviews must be a positive integer, got: {max_reviews}")

    if targets is not None:
        if len(targets) == 0:
            fail("Stage A - Argument Validation", "At least one target must be provided when --target is used.")
        for cat, src, tgt in targets:
            cat_clean = str(cat).strip()
            src_clean = str(src).strip().lower()
            tgt_clean = str(tgt).strip()
            if not cat_clean or cat_clean == "-1":
                fail("Stage A - Argument Validation", "Category cannot be empty or '-1'.")
            if not tgt_clean or tgt_clean == "-1":
                fail("Stage A - Argument Validation", "Target cannot be empty or '-1'.")
            if src_clean not in VALID_SOURCES:
                fail(
                    "Stage A - Argument Validation",
                    f"Invalid source '{src}'. Supported sources: youtube, reddit, googleplay, steam (or codes 1-4).",
                )


def generate_run_id() -> str:
    """Generate a collision-safe unique run ID."""
    timestamp = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    unique_suffix = uuid.uuid4().hex[:6]
    return f"{timestamp}_{unique_suffix}"


def parse_base_command(cmd: List[str]) -> Tuple[List[List[str]], Optional[str], List[str], List[str]]:
    """Parse container base command into components."""
    i = 0
    targets: List[List[str]] = []
    max_reviews: Optional[str] = None
    output_args: List[str] = []
    other_args: List[str] = []

    while i < len(cmd):
        arg = cmd[i]
        if arg == "--target":
            if i + 3 < len(cmd):
                targets.append([cmd[i + 1], cmd[i + 2], cmd[i + 3]])
                i += 4
            else:
                other_args.append(arg)
                i += 1
        elif arg == "--max-reviews":
            if i + 1 < len(cmd):
                max_reviews = cmd[i + 1]
                i += 2
            else:
                i += 1
        elif arg.startswith("--max-reviews="):
            max_reviews = arg.split("=", 1)[1]
            i += 1
        elif arg == "--output":
            if i + 1 < len(cmd):
                output_args = [arg, cmd[i + 1]]
                i += 2
            else:
                output_args = [arg]
                i += 1
        elif arg.startswith("--output="):
            output_args = [arg]
            i += 1
        else:
            other_args.append(arg)
            i += 1

    return targets, max_reviews, output_args, other_args


def build_command_override(
    base_command: List[str],
    targets: Optional[List[List[str]]],
    max_reviews: Optional[int],
) -> Optional[List[str]]:
    """Construct command override list, preserving default arguments if not overridden."""
    if targets is None and max_reviews is None:
        return None

    base_targets, base_max_reviews, output_args, other_args = parse_base_command(base_command)

    effective_targets = targets if targets is not None else base_targets
    effective_max_reviews = str(max_reviews) if max_reviews is not None else base_max_reviews

    new_cmd: List[str] = []
    for cat, src, tgt in effective_targets:
        new_cmd.extend(["--target", str(cat), str(src), str(tgt)])

    if effective_max_reviews is not None:
        new_cmd.extend(["--max-reviews", str(effective_max_reviews)])

    if output_args:
        new_cmd.extend(output_args)
    else:
        new_cmd.extend(["--output", "/app/output/Checkpoint1.csv"])

    new_cmd.extend(other_args)
    return new_cmd


def build_container_overrides(
    base_command: List[str],
    targets: Optional[List[List[str]]],
    max_reviews: Optional[int],
    run_id: str,
) -> Dict[str, Any]:
    """Build containerOverrides dictionary for ECS run_task."""
    override: Dict[str, Any] = {
        "name": CONTAINER_NAME,
        "environment": [
            {"name": "RUN_ID", "value": run_id},
        ],
    }
    cmd_override = build_command_override(base_command, targets, max_reviews)
    if cmd_override is not None:
        override["command"] = cmd_override
    return override


def verify_outputs(local_output_dir: Path) -> Tuple[int, int]:
    """Verify Checkpoint 2 and Checkpoint 3 exist, are non-empty, and match expected schemas."""
    checkpoint2_file = local_output_dir / "Checkpoint2.csv"
    checkpoint3_file = local_output_dir / "complete_data.csv"

    if not checkpoint2_file.exists() or checkpoint2_file.stat().st_size == 0:
        fail("Stage G - Output Verification", f"Missing or empty Checkpoint 2 file: {checkpoint2_file}")
    if not checkpoint3_file.exists() or checkpoint3_file.stat().st_size == 0:
        fail("Stage G - Output Verification", f"Missing or empty Checkpoint 3 file: {checkpoint3_file}")

    try:
        df_c2 = pd.read_csv(checkpoint2_file)
    except Exception as exc:
        fail("Stage G - Output Verification", f"Failed to read Checkpoint 2 CSV: {exc}")

    try:
        df_c3 = pd.read_csv(checkpoint3_file)
    except Exception as exc:
        fail("Stage G - Output Verification", f"Failed to read Checkpoint 3 CSV: {exc}")

    if list(df_c2.columns) != EXPECTED_CHECKPOINT2_COLUMNS:
        fail(
            "Stage G - Output Verification",
            f"Checkpoint 2 schema mismatch.\nExpected ({len(EXPECTED_CHECKPOINT2_COLUMNS)} cols): {EXPECTED_CHECKPOINT2_COLUMNS}\nGot ({len(df_c2.columns)} cols): {list(df_c2.columns)}",
        )

    if list(df_c3.columns) != EXPECTED_CHECKPOINT3_COLUMNS:
        fail(
            "Stage G - Output Verification",
            f"Checkpoint 3 schema mismatch.\nExpected ({len(EXPECTED_CHECKPOINT3_COLUMNS)} cols): {EXPECTED_CHECKPOINT3_COLUMNS}\nGot ({len(df_c3.columns)} cols): {list(df_c3.columns)}",
        )

    return len(df_c2), len(df_c3)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sentiment Analysis Automation - On-Demand Workflow Orchestrator"
    )
    parser.add_argument(
        "--target",
        nargs=3,
        action="append",
        metavar=("CATEGORY", "SOURCE", "TARGET"),
        help="Add a scrape target triple: CATEGORY SOURCE TARGET (e.g. --target zepto googleplay com.zeptoconsumerapp). Can be specified multiple times.",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=None,
        help="Maximum reviews to collect per target (uses task definition default of 2 if omitted).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and display planned ECS task configuration without launching AWS resources.",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # -----------------------------------------------------------------------
    # Stage A: Validate local prerequisites & input arguments
    # -----------------------------------------------------------------------
    if not ML_PYTHON_EXE.exists():
        fail("Stage A - Local Prerequisites", f"ML Python interpreter not found at: {ML_PYTHON_EXE}")
    if not ML_PIPELINE_SCRIPT.exists():
        fail("Stage A - Local Prerequisites", f"ML pipeline script not found at: {ML_PIPELINE_SCRIPT}")

    validate_inputs(args.target, args.max_reviews)

    # -----------------------------------------------------------------------
    # Stage B: Generate collision-safe unique run ID
    # -----------------------------------------------------------------------
    run_id = generate_run_id()
    s3_key = f"raw/run_id={run_id}/Checkpoint1.csv"

    local_data_dir = PROJECT_ROOT / "data" / run_id
    local_input_csv = local_data_dir / "Checkpoint1.csv"
    local_output_dir = PROJECT_ROOT / "output" / run_id

    print("============================================================")
    print("Sentiment Analysis On-Demand Runner")
    print(f"Run ID          : {run_id}")
    print(f"Scraper Targets : {args.target if args.target is not None else 'Task Definition Defaults'}")
    print(f"Max Reviews     : {args.max_reviews if args.max_reviews is not None else 'Task Definition Default (2)'}")
    print(f"Target S3 URI   : s3://{S3_BUCKET}/{s3_key}")
    print(f"Local Data Dir  : {local_data_dir}")
    print(f"Local Output Dir: {local_output_dir}")
    print("============================================================")

    # Initialize AWS session using verified profile and region
    try:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        ecs = session.client("ecs")
        s3 = session.client("s3")
    except (BotoCoreError, ClientError) as exc:
        fail("AWS Initialization", f"Could not initialize AWS session (profile='{AWS_PROFILE}'): {exc}")

    # Inspect task definition to read base command
    try:
        td = ecs.describe_task_definition(taskDefinition=TASK_DEFINITION)["taskDefinition"]
        c_defs = td.get("containerDefinitions", [])
        main_def = next((c for c in c_defs if c.get("name") == CONTAINER_NAME), c_defs[0] if c_defs else {})
        base_command = main_def.get("command", [])
        if not base_command:
            fail("AWS Configuration", f"No existing command found on container '{CONTAINER_NAME}' in {TASK_DEFINITION}.")
    except (BotoCoreError, ClientError) as exc:
        fail("AWS Configuration", f"Failed to inspect task definition {TASK_DEFINITION}: {exc}")

    container_override = build_container_overrides(base_command, args.target, args.max_reviews, run_id)

    # Dry-run check: validate and print without calling run_task
    if args.dry_run:
        print("\n[DRY RUN] Local prerequisites and AWS configuration validated successfully.")
        print(f"[DRY RUN] Cluster            : {ECS_CLUSTER}")
        print(f"[DRY RUN] Task Definition    : {TASK_DEFINITION}")
        print(f"[DRY RUN] Container Overrides: {container_override}")
        print("[DRY RUN] No AWS resources were launched.")
        return

    # -----------------------------------------------------------------------
    # Stage C: Start the existing Fargate ECS task
    # -----------------------------------------------------------------------
    print(f"\n[Stage C] Starting ECS Fargate task ({TASK_DEFINITION}) on cluster '{ECS_CLUSTER}'...")
    if "command" in container_override:
        print(f"          Command override: {container_override['command']}")
    else:
        print("          Using registered default command from task definition.")

    try:
        run_resp = ecs.run_task(
            cluster=ECS_CLUSTER,
            taskDefinition=TASK_DEFINITION,
            launchType="FARGATE",
            count=1,
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": SUBNETS,
                    "securityGroups": SECURITY_GROUPS,
                    "assignPublicIp": "ENABLED",
                }
            },
            overrides={
                "containerOverrides": [container_override],
            },
        )
    except (BotoCoreError, ClientError) as exc:
        fail("Stage C - Start ECS Task", f"ECS run_task API call failed: {exc}")

    failures = run_resp.get("failures", [])
    tasks = run_resp.get("tasks", [])
    if failures or not tasks:
        fail("Stage C - Start ECS Task", f"Failed to launch task. ECS failures: {failures}")

    task_arn = tasks[0]["taskArn"]
    print(f"          Task ARN: {task_arn}")

    # -----------------------------------------------------------------------
    # Stage D: Monitor the ECS task
    # -----------------------------------------------------------------------
    print("\n[Stage D] Monitoring ECS Fargate scraper task...")
    last_status = None
    task_info = None

    while True:
        try:
            desc_resp = ecs.describe_tasks(cluster=ECS_CLUSTER, tasks=[task_arn])
            desc_tasks = desc_resp.get("tasks", [])
            if not desc_tasks:
                fail("Stage D - Monitor ECS Task", f"Task {task_arn} could not be found via describe_tasks.")
            task_info = desc_tasks[0]
        except (BotoCoreError, ClientError) as exc:
            fail("Stage D - Monitor ECS Task", f"Error polling task status: {exc}")

        current_status = task_info.get("lastStatus", "UNKNOWN")
        if current_status != last_status:
            print(f"          Task status: {current_status}")
            last_status = current_status

        if current_status == "STOPPED":
            break

        time.sleep(POLL_INTERVAL_SECONDS)

    stopped_reason = task_info.get("stoppedReason", "")
    containers = task_info.get("containers", [])
    container_info = next((c for c in containers if c.get("name") == CONTAINER_NAME), containers[0] if containers else {})
    exit_code = container_info.get("exitCode")
    container_reason = container_info.get("reason", "")

    if exit_code != 0:
        fail(
            "Stage D - ECS Scraper Execution",
            f"Scraper container '{CONTAINER_NAME}' failed with exitCode={exit_code}. "
            f"StoppedReason='{stopped_reason}' ContainerReason='{container_reason}'. "
            "Aborting before ML pipeline.",
        )

    print(f"          Scraper container exited successfully (exitCode=0).")

    # -----------------------------------------------------------------------
    # Stage E: Download the exact Checkpoint 1 file
    # -----------------------------------------------------------------------
    print(f"\n[Stage E] Locating and downloading s3://{S3_BUCKET}/{s3_key}...")
    try:
        head = s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
        size_bytes = head.get("ContentLength", 0)
        if size_bytes <= 0:
            fail("Stage E - S3 Verification", f"S3 object s3://{S3_BUCKET}/{s3_key} is empty (0 bytes).")
    except ClientError as exc:
        fail(
            "Stage E - S3 Verification",
            f"Expected dataset s3://{S3_BUCKET}/{s3_key} was not found in S3: {exc}",
        )

    local_data_dir.mkdir(parents=True, exist_ok=True)
    try:
        s3.download_file(S3_BUCKET, s3_key, str(local_input_csv))
    except (BotoCoreError, ClientError) as exc:
        fail("Stage E - S3 Download", f"Failed to download dataset to {local_input_csv}: {exc}")

    if not local_input_csv.exists() or local_input_csv.stat().st_size == 0:
        fail("Stage E - S3 Download", f"Downloaded file is missing or empty at: {local_input_csv}")

    df_c1 = pd.read_csv(local_input_csv)
    print(f"          Downloaded ({size_bytes} bytes, {len(df_c1)} rows, {len(df_c1.columns)} cols) to: {local_input_csv}")

    # -----------------------------------------------------------------------
    # Stage F: Run the local ML pipeline
    # -----------------------------------------------------------------------
    print(f"\n[Stage F] Running local ML pipeline via {ML_PYTHON_EXE}...")
    local_output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(ML_PYTHON_EXE),
        str(ML_PIPELINE_SCRIPT),
        "--input",
        str(local_input_csv),
        "--output-dir",
        str(local_output_dir),
    ]

    result = subprocess.run(cmd)
    if result.returncode != 0:
        fail(
            "Stage F - Local ML Pipeline",
            f"ML pipeline exited with non-zero code {result.returncode}.",
            exit_code=result.returncode,
        )

    # -----------------------------------------------------------------------
    # Stage G: Verify outputs and stop
    # -----------------------------------------------------------------------
    print("\n[Stage G] Verifying generated checkpoints and schemas...")
    c2_rows, c3_rows = verify_outputs(local_output_dir)

    checkpoint2_file = local_output_dir / "Checkpoint2.csv"
    checkpoint3_file = local_output_dir / "complete_data.csv"

    print("          Checkpoint 2 schema and contents verified.")
    print("          Checkpoint 3 schema and contents verified.")

    print("\n============================================================")
    print("SUCCESS: Full workflow completed successfully!")
    print(f"  Run ID       : {run_id}")
    print(f"  S3 Source    : s3://{S3_BUCKET}/{s3_key}")
    print(f"  Checkpoint 1 : {local_input_csv} ({len(df_c1)} rows, {len(df_c1.columns)} cols)")
    print(f"  Checkpoint 2 : {checkpoint2_file} ({c2_rows} rows, {len(EXPECTED_CHECKPOINT2_COLUMNS)} cols)")
    print(f"  Checkpoint 3 : {checkpoint3_file} ({c3_rows} rows, {len(EXPECTED_CHECKPOINT3_COLUMNS)} cols)")
    print("============================================================")


if __name__ == "__main__":
    main()
