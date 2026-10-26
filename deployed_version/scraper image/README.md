# Auto Sentiment Scraper (Docker + AWS ECS Fargate)

Minimal, standalone multi-platform review scraper that extracts reviews/comments from **YouTube**, **Reddit**, **Google Play**, and **Steam**, normalizes dates and metadata into the 8-column `Checkpoint1.csv` format, and saves either to the local filesystem or directly to Amazon S3.

---

## Project Files

- `scraper.py` — Standalone scraper script (YouTube, Reddit, Google Play, Steam, date normalization, deduplication, local + S3 output).
- `Dockerfile.scraper` — Lightweight `python:3.10-slim` container definition.
- `requirements-scraper.txt` — Minimal Python dependencies (`boto3`, `google-play-scraper`, `pandas`, `python-dateutil`, `requests`, `youtube-comment-downloader`).
- `.dockerignore` — Keeps the Docker build context clean.
- `test_scraper.py` — Unit tests for `scraper.py`.

---

## Supported Sources

| Source Name | Numeric Alias | Target Format | Domain Mapped |
| :--- | :--- | :--- | :--- |
| `youtube` | `1` | Full YouTube video URL | `media` |
| `reddit` | `2` | Full Reddit thread URL | `community` |
| `googleplay` | `3` | Google Play package ID (e.g. `com.zeptoconsumerapp`) | `apps` |
| `steam` | `4` | Steam numeric App ID (e.g. `730`) | `gaming` |

---

## Configuration (CLI Flags & Environment Variables)

| Purpose | CLI Argument | Environment Variable | Default |
| :--- | :--- | :--- | :--- |
| Scrape targets | `--target <category> <source> <target>` (repeatable) or `--config-json '<json>'` | `SCRAPER_CONFIG_JSON` (JSON list or `{"targets": [...]}`) | Required |
| Max reviews per target | `--max-reviews <int>` | Per-target `max_reviews` in `SCRAPER_CONFIG_JSON` | Platform default (`2000` GP / `200` Steam / all YT & Reddit) |
| Local output file path | `--output <path>` | `OUTPUT_PATH` | `Checkpoint1.csv` |
| S3 Bucket (enables S3 upload) | `--s3-bucket <bucket>` | `S3_BUCKET_NAME` | None (writes locally if unset) |
| Custom S3 Object Key | `--s3-key <key>` | `S3_KEY` | `raw/run_id=<RUN_ID>/Checkpoint1.csv` |
| Run ID | `--run-id <id>` | `RUN_ID` | `run_YYYYMMDD_HHMMSS` |
| AWS Region | `--aws-region <region>` | `AWS_REGION` | `ap-southeast-2` |

---

## 1. Local Execution (Python)

```powershell
python scraper.py `
  --target zepto googleplay com.zeptoconsumerapp `
  --target cs2 steam 730 `
  --max-reviews 20 `
  --output Checkpoint1.csv
```

Run unit tests:

```powershell
python -m unittest test_scraper.py -v
```

---

## 2. Local Docker Build & Test

### Build Image
```powershell
docker build -f Dockerfile.scraper -t auto-sentiment-scraper:latest .
```

### Run Locally in Docker (Saves CSV to Host via Bind Mount)
```powershell
mkdir -Force .\output

docker run --rm `
  -v "${PWD}/output:/app/output" `
  auto-sentiment-scraper:latest `
  --target zepto googleplay com.zeptoconsumerapp `
  --target cs2 steam 730 `
  --max-reviews 10 `
  --output /app/output/Checkpoint1.csv
```

---

## 3. Push Image to Existing Amazon ECR Repository

Replace region/account/repository values if needed (shown below for `ap-southeast-2` and account `127228002846`):

```powershell
# 1. Authenticate Docker with ECR
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin 127228002846.dkr.ecr.ap-southeast-2.amazonaws.com

# 2. Tag local image for ECR
docker tag auto-sentiment-scraper:latest 127228002846.dkr.ecr.ap-southeast-2.amazonaws.com/auto-sentiment-scraper:latest

# 3. Push image to ECR
docker push 127228002846.dkr.ecr.ap-southeast-2.amazonaws.com/auto-sentiment-scraper:latest
```

---

## 4. Run One-Off Task on AWS ECS Fargate

### Required Task Role S3 IAM Permission
Attach this minimal policy to your ECS **Task Role** (distinct from `ecsTaskExecutionRole`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*"
    }
  ]
}
```

### Trigger One-Off Fargate Task (`aws ecs run-task`)
```powershell
aws ecs run-task `
  --region ap-southeast-2 `
  --cluster YOUR_ECS_CLUSTER_NAME `
  --task-definition auto-sentiment-scraper `
  --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxxxxx],securityGroups=[sg-xxxxxxxx],assignPublicIp=ENABLED}" `
  --overrides '{
    "containerOverrides": [
      {
        "name": "scraper",
        "environment": [
          {"name": "S3_BUCKET_NAME", "value": "YOUR_BUCKET_NAME"},
          {"name": "SCRAPER_CONFIG_JSON", "value": "[{\"category\":\"zepto\",\"source\":\"googleplay\",\"target\":\"com.zeptoconsumerapp\",\"max_reviews\":200},{\"category\":\"cs2\",\"source\":\"steam\",\"target\":\"730\",\"max_reviews\":200}]"}
        ]
      }
    ]
  }'
```
