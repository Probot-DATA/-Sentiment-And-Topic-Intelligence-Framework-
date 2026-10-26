#!/usr/bin/env python3
"""Standalone non-interactive multi-platform scraper for Local and AWS ECS Fargate execution."""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("scraper")

SOURCE_CODE_MAP: Dict[str, str] = {
    "1": "youtube",
    "2": "reddit",
    "3": "googleplay",
    "4": "steam",
}
SOURCE_ALIASES: Dict[str, str] = {
    "yt": "youtube",
    "google_play": "googleplay",
    "playstore": "googleplay",
}
VALID_SOURCES = frozenset(SOURCE_CODE_MAP.values())

DOMAIN_MAP: Dict[str, str] = {
    "youtube": "media",
    "reddit": "community",
    "googleplay": "apps",
    "steam": "gaming",
}

CHECKPOINT1_COLUMNS: List[str] = [
    "url",
    "author",
    "Text",
    "date",
    "source",
    "category",
    "parsed_date",
    "domain",
]


# ---------------------------------------------------------------------------
# 1. HTTP Helper & Platform Scrapers (Preserved from Notebook Cell 1)
# ---------------------------------------------------------------------------
def safe_request(
    url: str,
    headers: Dict[str, str],
    retries: int = 3,
    timeout: int = 10,
    params: Optional[Dict[str, Any]] = None,
    session: Optional[Any] = None,
) -> Optional[requests.Response]:
    """Perform an HTTP GET request with bounded retries and timeout."""
    http = session or requests
    for i in range(retries):
        try:
            return http.get(url, headers=headers, params=params, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            logger.warning("Retry %d/%d failed for %s: %s", i + 1, retries, url, exc)
            if i + 1 < retries:
                time.sleep(2)
    return None


def extract_youtube(
    url: str,
    max_reviews: Optional[int] = None,
    extractor: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Extract YouTube comments using youtube_comment_downloader."""
    if extractor is None:
        from youtube_comment_downloader import YoutubeCommentDownloader

        extractor = YoutubeCommentDownloader()

    comments = extractor.get_comments_from_url(url)
    temp: List[Dict[str, Any]] = []
    for c in comments:
        # Prefer authoritative parsed timestamp if available from extractor
        raw_time = c.get("time_parsed") if c.get("time_parsed") is not None else c.get("time")
        temp.append(
            {
                "url": url,
                "author": c.get("author"),
                "Text": c.get("text"),
                "date": raw_time,
                "source": "youtube",
            }
        )
        if max_reviews is not None and len(temp) >= max_reviews:
            break
    return temp


def extract_reddit(
    url: str,
    max_reviews: Optional[int] = None,
    session: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Extract Reddit comments from thread JSON endpoint."""
    original_url = url
    json_url = url.rstrip("/") + ".json"
    headers = {"User-Agent": "MyRedditApp/1.0 (by u/yourusername)"}

    response = safe_request(json_url, headers, session=session)
    if response is None:
        logger.error("Reddit request failed after retries: %s", url)
        return []
    if response.status_code != 200:
        logger.error("Reddit status error %d for %s", response.status_code, url)
        return []

    try:
        data_json = response.json()
    except Exception:
        logger.warning("Invalid JSON from Reddit (possibly blocked): %s", url)
        return []

    temp: List[Dict[str, Any]] = []
    try:
        comments = data_json[1]["data"]["children"]
        for c in comments:
            c_data = c.get("data", {})
            body = c_data.get("body")
            if body:
                temp.append(
                    {
                        "url": original_url,
                        "author": c_data.get("author"),
                        "Text": body,
                        "date": c_data.get("created_utc"),
                        "source": "reddit",
                    }
                )
                if max_reviews is not None and len(temp) >= max_reviews:
                    break
    except Exception as exc:
        raise ValueError(f"Unexpected Reddit JSON structure for {url}") from exc

    return temp


def extract_google_play(
    app_id: str,
    count: int = 2000,
    reviews_fn: Optional[Callable[..., Any]] = None,
) -> List[Dict[str, Any]]:
    """Extract Google Play Store reviews using google_play_scraper."""
    if reviews_fn is None:
        from google_play_scraper import Sort, reviews

        result, _ = reviews(app_id, count=count, sort=Sort.NEWEST)
    else:
        result, _ = reviews_fn(app_id, count=count)

    temp: List[Dict[str, Any]] = []
    for r in result[:count]:
        temp.append(
            {
                "url": f"googleplay_{app_id}",
                "author": r.get("userName"),
                "Text": r.get("content"),
                "date": r.get("at"),
                "source": "googleplay",
            }
        )
    return temp


def extract_steam(
    app_id: str,
    total_reviews: int = 200,
    session: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Extract Steam reviews using the store.steampowered.com appreviews endpoint."""
    url = f"https://store.steampowered.com/appreviews/{app_id}"
    params: Dict[str, Any] = {
        "json": 1,
        "language": "english",
        "num_per_page": min(100, max(1, total_reviews)),
    }
    headers = {"User-Agent": "Mozilla/5.0"}

    all_reviews: List[Dict[str, Any]] = []
    cursor: Optional[str] = "*"
    seen_cursors = set()

    while len(all_reviews) < total_reviews:
        if not cursor or cursor in seen_cursors:
            break
        seen_cursors.add(cursor)
        params["cursor"] = cursor

        response = safe_request(url, headers, params=params, session=session)
        if response is None or response.status_code != 200:
            logger.error("Steam request failed for app_id=%s", app_id)
            break

        res = response.json()
        batch = res.get("reviews", [])
        if not batch:
            break

        for r in batch:
            all_reviews.append(
                {
                    "url": f"steam_{app_id}",
                    "author": r.get("author", {}).get("steamid"),
                    "Text": r.get("review"),
                    "date": r.get("timestamp_created"),
                    "source": "steam",
                }
            )
        cursor = res.get("cursor")

    return all_reviews[:total_reviews]


# ---------------------------------------------------------------------------
# 2. Date Normalization & ISO 8601 UTC Formatting
# ---------------------------------------------------------------------------
def convert_relative_time(
    value: Any, scraped_date: Optional[datetime] = None
) -> Optional[datetime]:
    """Convert raw platform timestamps, Unix epoch numbers, or relative time strings into UTC datetime objects."""
    if value is None or pd.isna(value):
        return None

    if scraped_date is None:
        ref = datetime.now(timezone.utc)
    elif isinstance(scraped_date, datetime):
        ref = scraped_date if scraped_date.tzinfo else scraped_date.replace(tzinfo=timezone.utc)
    else:
        ref = pd.to_datetime(scraped_date, utc=True).to_pydatetime()

    # 1. Handle Python datetime / Timestamp objects
    if isinstance(value, (datetime, pd.Timestamp)):
        dt = value.to_pydatetime() if isinstance(value, pd.Timestamp) else value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    # 2. Handle Unix timestamps (int, float, or numeric string such as '1770694597.0' or '1710000000')
    is_numeric = False
    num_val: Optional[float] = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        is_numeric = True
        num_val = float(value)
    elif isinstance(value, str):
        s_val = value.strip()
        if re.match(r"^-?\d+(\.\d+)?$", s_val):
            try:
                num_val = float(s_val)
                is_numeric = True
            except ValueError:
                pass

    if is_numeric and num_val is not None:
        try:
            abs_v = abs(num_val)
            # Automatic unit detection
            if abs_v >= 1e16:
                secs = num_val / 1e9  # nanoseconds
            elif abs_v >= 1e13:
                secs = num_val / 1e6  # microseconds
            elif abs_v >= 1e11:
                secs = num_val / 1e3  # milliseconds
            else:
                secs = num_val  # seconds
            return datetime.fromtimestamp(secs, tz=timezone.utc)
        except (OverflowError, ValueError, OSError):
            return None

    # 3. String cleanup and relative date parsing
    val_str = str(value).strip()
    if not val_str or val_str.lower() in ("none", "nan", "null", "nat", "<na>"):
        return None

    cleaned = (
        val_str.lower()
        .replace("\xa0", " ")
        .replace("(edited)", "")
        .replace("edited", "")
        .replace("ago", "")
        .replace("•", "")
        .strip()
    )

    if cleaned in ("", "just now", "now", "moments"):
        if cleaned == "":
            return None
        return ref

    if "yesterday" in cleaned:
        return ref - timedelta(days=1)

    match = re.search(r"(\d+)", cleaned)
    if match:
        num = int(match.group(1))
        if any(x in cleaned for x in ["sec", "second"]):
            return ref - timedelta(seconds=num)
        if any(x in cleaned for x in ["min", "mins", "minute"]):
            return ref - timedelta(minutes=num)
        if any(x in cleaned for x in ["hr", "hrs", "hour"]):
            return ref - timedelta(hours=num)
        if "day" in cleaned:
            return ref - timedelta(days=num)
        if "week" in cleaned:
            return ref - timedelta(weeks=num)
        if any(x in cleaned for x in ["mo", "month"]):
            dt = (pd.to_datetime(ref) - pd.DateOffset(months=num)).to_pydatetime()
            return dt.astimezone(timezone.utc)
        if any(x in cleaned for x in ["yr", "year"]):
            dt = (pd.to_datetime(ref) - pd.DateOffset(years=num)).to_pydatetime()
            return dt.astimezone(timezone.utc)

    # 4. Fallback: Parse standard absolute date strings
    try:
        parsed = pd.to_datetime(val_str, errors="coerce", utc=True)
        if pd.isna(parsed):
            return None
        return parsed.to_pydatetime()
    except Exception:
        return None


def format_iso8601_utc(dt: Optional[datetime]) -> Optional[str]:
    """Format a datetime object as a UTC ISO 8601 string (YYYY-MM-DDTHH:MM:SSZ)."""
    if dt is None:
        return None
    if isinstance(dt, pd.Timestamp):
        dt = dt.to_pydatetime()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# 3. Target Validation & Execution
# ---------------------------------------------------------------------------
def normalize_source(raw_source: str) -> str:
    """Validate and normalize a source name or numeric code ('1'-'4')."""
    s = str(raw_source).strip().lower()
    s = SOURCE_CODE_MAP.get(s, SOURCE_ALIASES.get(s, s))
    if s not in VALID_SOURCES:
        raise ValueError(
            f"Invalid source '{raw_source}'. Supported sources: {sorted(VALID_SOURCES)} (or codes 1-4)."
        )
    return s


def parse_targets(
    cli_targets: Optional[Sequence[Sequence[str]]] = None,
    config_json: Optional[str] = None,
    default_max_reviews: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Parse and validate target triples from CLI flags and/or SCRAPER_CONFIG_JSON."""
    targets: List[Dict[str, Any]] = []

    if config_json:
        payload = json.loads(config_json)
        items = payload.get("targets", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise ValueError("SCRAPER_CONFIG_JSON must be a JSON list or object with a 'targets' list.")
        for item in items:
            category = str(item.get("category", "")).strip()
            target = str(item.get("target", "")).strip()
            if not category or category == "-1" or not target or target == "-1":
                raise ValueError("Each target requires non-empty 'category' and 'target'.")
            limit = item.get("max_reviews", default_max_reviews)
            if limit is not None and int(limit) <= 0:
                raise ValueError("max_reviews must be a positive integer.")
            targets.append(
                {
                    "category": category,
                    "source": normalize_source(item.get("source", "")),
                    "target": target,
                    "max_reviews": int(limit) if limit is not None else None,
                }
            )

    if cli_targets:
        if default_max_reviews is not None and int(default_max_reviews) <= 0:
            raise ValueError("--max-reviews must be a positive integer.")
        for cat, src, tgt in cli_targets:
            category = str(cat).strip()
            target = str(tgt).strip()
            if not category or category == "-1" or not target or target == "-1":
                raise ValueError("Each --target requires non-empty CATEGORY and TARGET.")
            targets.append(
                {
                    "category": category,
                    "source": normalize_source(src),
                    "target": target,
                    "max_reviews": int(default_max_reviews) if default_max_reviews is not None else None,
                }
            )

    if not targets:
        raise ValueError("No scraping targets provided. Supply --target or SCRAPER_CONFIG_JSON.")

    return targets


def run_scraper(
    targets: Sequence[Dict[str, Any]],
    google_play_count: int = 2000,
    steam_total_reviews: int = 200,
    rate_limit_sec: float = 1.5,
    scraped_date: Optional[datetime] = None,
    extractors: Optional[Dict[str, Callable[[str, Optional[int]], List[Dict[str, Any]]]]] = None,
) -> pd.DataFrame:
    """Run all configured scrape targets and return the 8-column Checkpoint1 DataFrame."""
    semidata: Dict[str, str] = {}
    url_source_map: Dict[str, str] = {}
    max_reviews_map: Dict[str, Optional[int]] = {}

    for t in targets:
        src = t["source"]
        raw_tgt = t["target"]
        key = f"{src}_{raw_tgt}" if src in ("googleplay", "steam") else raw_tgt
        semidata[key] = t["category"]
        url_source_map[key] = src
        max_reviews_map[key] = t.get("max_reviews")

    data: List[Dict[str, Any]] = []
    for idx, (key, source) in enumerate(url_source_map.items()):
        limit = max_reviews_map.get(key)
        try:
            logger.info("Scraping source=%s key=%s category=%s", source, key, semidata[key])
            if extractors and source in extractors:
                rows = extractors[source](key, limit)
            elif source == "youtube":
                rows = extract_youtube(key, max_reviews=limit)
            elif source == "reddit":
                rows = extract_reddit(key, max_reviews=limit)
            elif source == "googleplay":
                app_id = key.split("_", 1)[1]
                rows = extract_google_play(
                    app_id,
                    count=limit if limit is not None else google_play_count,
                )
            elif source == "steam":
                app_id = key.split("_", 1)[1]
                rows = extract_steam(
                    app_id,
                    total_reviews=limit if limit is not None else steam_total_reviews,
                )
            else:
                raise ValueError(f"Unsupported source: {source}")

            if limit is not None:
                rows = rows[:limit]

            data.extend(rows)
            logger.info("Collected %d rows from %s", len(rows), key)
        except Exception as exc:
            logger.error("Error scraping %s (%s): %s", key, source, exc)

        if idx + 1 < len(url_source_map) and rate_limit_sec > 0:
            time.sleep(rate_limit_sec)

    if not data:
        return pd.DataFrame(columns=CHECKPOINT1_COLUMNS)

    ref_date = scraped_date or datetime.now(timezone.utc)
    df = pd.DataFrame(data)
    df["category"] = df["url"].map(semidata)
    df["parsed_date"] = df["date"].apply(
        lambda x: format_iso8601_utc(convert_relative_time(x, scraped_date=ref_date))
    )
    df["date"] = df["parsed_date"]
    df.drop_duplicates(subset=["Text", "url"], inplace=True)
    df = df.reset_index(drop=True)
    df["domain"] = df["source"].map(DOMAIN_MAP)
    return df[CHECKPOINT1_COLUMNS]


def save_output(
    df: pd.DataFrame,
    output_path: str = "Checkpoint1.csv",
    s3_bucket: str = "",
    s3_key: str = "",
    aws_region: str = "ap-southeast-2",
    run_id: str = "",
    s3_client: Optional[Any] = None,
) -> str:
    """Save DataFrame locally or upload to S3 when s3_bucket is provided."""
    missing = [col for col in CHECKPOINT1_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Output DataFrame is missing required Checkpoint1 columns: {missing}")

    bucket = (s3_bucket or "").strip()
    if bucket:
        effective_run = (run_id or "").strip() or datetime.now().strftime("run_%Y%m%d_%H%M%S")
        key = (s3_key or "").strip() or f"raw/run_id={effective_run}/Checkpoint1.csv"
        if s3_client is None:
            import boto3

            s3_client = boto3.client("s3", region_name=aws_region)

        buf = io.StringIO()
        df.to_csv(buf, index=False)
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=buf.getvalue().encode("utf-8"),
        )
        uri = f"s3://{bucket}/{key}"
        logger.info("Uploaded %d rows to %s", len(df), uri)
        return uri

    local_file = Path(output_path).resolve()
    local_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(local_file, index=False)
    logger.info("Saved %d rows locally to %s", len(df), local_file)
    return str(local_file)


# ---------------------------------------------------------------------------
# 4. CLI Entry Point
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Auto Sentiment Analyser - Standalone Multi-Platform Scraper (Local & AWS ECS Fargate)"
    )
    parser.add_argument(
        "--target",
        nargs=3,
        action="append",
        metavar=("CATEGORY", "SOURCE", "TARGET"),
        help="Add a scrape target triple: CATEGORY SOURCE TARGET (supported sources: youtube, reddit, googleplay, steam).",
    )
    parser.add_argument(
        "--config-json",
        default=None,
        help="Inline JSON configuration payload (or set SCRAPER_CONFIG_JSON).",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=None,
        help="Maximum reviews/comments to collect per target.",
    )
    parser.add_argument(
        "--output",
        default=os.getenv("OUTPUT_PATH", "Checkpoint1.csv"),
        help="Local CSV output path when S3_BUCKET_NAME is not set (default: Checkpoint1.csv).",
    )
    parser.add_argument(
        "--s3-bucket",
        default=os.getenv("S3_BUCKET_NAME", "").strip(),
        help="S3 bucket name for uploading Checkpoint1.csv (or set S3_BUCKET_NAME).",
    )
    parser.add_argument(
        "--s3-key",
        default=os.getenv("S3_KEY", "").strip(),
        help="Optional S3 object key override (default: raw/run_id=<RUN_ID>/Checkpoint1.csv).",
    )
    parser.add_argument(
        "--run-id",
        default=os.getenv("RUN_ID", "").strip(),
        help="Run identifier for S3 key partitioning (or set RUN_ID).",
    )
    parser.add_argument(
        "--aws-region",
        default=os.getenv("AWS_REGION", "ap-southeast-2"),
        help="AWS region for S3 upload (default: ap-southeast-2 or AWS_REGION).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config_json = args.config_json or os.getenv("SCRAPER_CONFIG_JSON")
        targets = parse_targets(
            cli_targets=args.target,
            config_json=config_json,
            default_max_reviews=args.max_reviews,
        )
    except Exception as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    df = run_scraper(targets=targets)
    if df.empty:
        logger.error("No rows collected across %d configured target(s).", len(targets))
        return 2

    try:
        destination = save_output(
            df=df,
            output_path=args.output,
            s3_bucket=args.s3_bucket,
            s3_key=args.s3_key,
            aws_region=args.aws_region,
            run_id=args.run_id,
        )
    except Exception as exc:
        logger.error("Failed to save output: %s", exc)
        return 2

    print(
        json.dumps(
            {
                "event": "scrape_completed",
                "rows": len(df),
                "destination": destination,
                "exit_code": 0,
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
