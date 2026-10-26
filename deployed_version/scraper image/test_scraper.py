"""Unit tests for the standalone scraper.py module."""

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

import scraper


class TestScraper(unittest.TestCase):
    """Tests for source validation, extraction, normalization, and storage."""

    def test_normalize_source_valid(self):
        self.assertEqual(scraper.normalize_source("1"), "youtube")
        self.assertEqual(scraper.normalize_source("youtube"), "youtube")
        self.assertEqual(scraper.normalize_source("2"), "reddit")
        self.assertEqual(scraper.normalize_source("reddit"), "reddit")
        self.assertEqual(scraper.normalize_source("3"), "googleplay")
        self.assertEqual(scraper.normalize_source("googleplay"), "googleplay")
        self.assertEqual(scraper.normalize_source("4"), "steam")
        self.assertEqual(scraper.normalize_source("steam"), "steam")

    def test_normalize_source_rejects_amazon_and_invalid(self):
        with self.assertRaises(ValueError) as ctx:
            scraper.normalize_source("amazon")
        self.assertIn("Invalid source 'amazon'", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            scraper.normalize_source("5")
        self.assertIn("Invalid source '5'", str(ctx.exception))

        with self.assertRaises(ValueError):
            scraper.normalize_source("twitter")

    def test_convert_relative_time(self):
        dt = scraper.convert_relative_time("2 days ago")
        self.assertIsInstance(dt, datetime)
        dt_iso = scraper.convert_relative_time("2025-01-15 10:30:00")
        self.assertEqual(dt_iso.year, 2025)
        self.assertEqual(dt_iso.month, 1)
        self.assertEqual(dt_iso.day, 15)

    def test_reported_defects_and_iso_normalization(self):
        """Test the two specific reported defects: '3 months ago' and '1770694597.0'."""
        ref = datetime(2026, 10, 22, 12, 0, 0, tzinfo=scraper.timezone.utc)

        # Defect 1: '3 months ago'
        dt1 = scraper.convert_relative_time("3 months ago", scraped_date=ref)
        self.assertIsNotNone(dt1)
        self.assertEqual(scraper.format_iso8601_utc(dt1), "2026-07-22T12:00:00Z")

        dt1_edited = scraper.convert_relative_time("3 months ago (edited)", scraped_date=ref)
        self.assertEqual(scraper.format_iso8601_utc(dt1_edited), "2026-07-22T12:00:00Z")

        # Defect 2: '1770694597.0' (float string) and float 1770694597.0
        dt2_str = scraper.convert_relative_time("1770694597.0")
        self.assertIsNotNone(dt2_str)
        self.assertEqual(scraper.format_iso8601_utc(dt2_str), "2026-02-10T03:36:37Z")

        dt2_float = scraper.convert_relative_time(1770694597.0)
        self.assertEqual(scraper.format_iso8601_utc(dt2_float), "2026-02-10T03:36:37Z")

    def test_unix_timestamp_unit_detection(self):
        """Test timestamp unit detection for seconds, milliseconds, microseconds, nanoseconds."""
        # Seconds
        dt_s = scraper.convert_relative_time(1710000000)
        self.assertEqual(scraper.format_iso8601_utc(dt_s), "2024-03-09T16:00:00Z")

        # Milliseconds (13 digits)
        dt_ms = scraper.convert_relative_time(1710000000000)
        self.assertEqual(scraper.format_iso8601_utc(dt_ms), "2024-03-09T16:00:00Z")

        # Microseconds (16 digits)
        dt_us = scraper.convert_relative_time(1710000000000000)
        self.assertEqual(scraper.format_iso8601_utc(dt_us), "2024-03-09T16:00:00Z")

    def test_ordinary_and_iso_dates(self):
        """Test ordinary datetime strings, Python datetime objects, and ISO strings."""
        dt_str = scraper.convert_relative_time("2026-04-27 17:18:04")
        self.assertEqual(scraper.format_iso8601_utc(dt_str), "2026-04-27T17:18:04Z")

        dt_obj = scraper.convert_relative_time(datetime(2026, 4, 27, 17, 18, 4))
        self.assertEqual(scraper.format_iso8601_utc(dt_obj), "2026-04-27T17:18:04Z")

    def test_missing_and_invalid_dates(self):
        """Test missing, None, NaN, and invalid dates safely produce None."""
        self.assertIsNone(scraper.convert_relative_time(None))
        self.assertIsNone(scraper.convert_relative_time(pd.NA))
        self.assertIsNone(scraper.convert_relative_time(""))
        self.assertIsNone(scraper.convert_relative_time("   "))
        self.assertIsNone(scraper.convert_relative_time("none"))
        self.assertIsNone(scraper.convert_relative_time("nan"))
        self.assertIsNone(scraper.convert_relative_time("null"))
        self.assertIsNone(scraper.convert_relative_time("completely invalid date"))

    def test_relative_date_variations(self):
        """Test relative dates like yesterday, just now, minutes, hours, days, weeks, years."""
        ref = datetime(2026, 10, 22, 12, 0, 0, tzinfo=scraper.timezone.utc)
        self.assertEqual(scraper.format_iso8601_utc(scraper.convert_relative_time("just now", scraped_date=ref)), "2026-10-22T12:00:00Z")
        self.assertEqual(scraper.format_iso8601_utc(scraper.convert_relative_time("yesterday", scraped_date=ref)), "2026-10-21T12:00:00Z")
        self.assertEqual(scraper.format_iso8601_utc(scraper.convert_relative_time("10 mins ago", scraped_date=ref)), "2026-10-22T11:50:00Z")
        self.assertEqual(scraper.format_iso8601_utc(scraper.convert_relative_time("2 hours ago", scraped_date=ref)), "2026-10-22T10:00:00Z")
        self.assertEqual(scraper.format_iso8601_utc(scraper.convert_relative_time("3 days ago", scraped_date=ref)), "2026-10-19T12:00:00Z")
        self.assertEqual(scraper.format_iso8601_utc(scraper.convert_relative_time("2 weeks ago", scraped_date=ref)), "2026-10-08T12:00:00Z")
        self.assertEqual(scraper.format_iso8601_utc(scraper.convert_relative_time("1 year ago", scraped_date=ref)), "2025-10-22T12:00:00Z")

    def test_extract_youtube_respects_max_reviews(self):
        fake_comments = [
            {"author": f"user{i}", "text": f"comment {i}", "time": "1 day ago"}
            for i in range(10)
        ]
        mock_dl = MagicMock()
        mock_dl.get_comments_from_url.return_value = iter(fake_comments)

        rows = scraper.extract_youtube(
            "https://youtube.com/watch?v=123", max_reviews=4, extractor=mock_dl
        )
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["source"], "youtube")
        self.assertEqual(rows[0]["url"], "https://youtube.com/watch?v=123")

    def test_extract_reddit_respects_max_reviews(self):
        fake_json = [
            {
                "data": {
                    "children": [
                        {
                            "data": {
                                "title": "Post Title",
                                "selftext": "Post Body",
                                "author": "op",
                                "created_utc": 1700000000,
                            }
                        }
                    ]
                }
            },
            {
                "data": {
                    "children": [
                        {
                            "kind": "t1",
                            "data": {
                                "body": f"reply {i}",
                                "author": f"u{i}",
                                "created_utc": 1700000100 + i,
                            },
                        }
                        for i in range(10)
                    ]
                }
            },
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_json
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        rows = scraper.extract_reddit(
            "https://www.reddit.com/r/test/comments/abc/thread/",
            max_reviews=3,
            session=mock_session,
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["source"], "reddit")

    def test_extract_google_play_url_key_and_cap(self):
        fake_reviews = [
            {
                "userName": f"gp{i}",
                "content": f"great app {i}",
                "at": datetime(2025, 2, 1, 12, 0, 0),
            }
            for i in range(5)
        ]
        rows = scraper.extract_google_play(
            "com.example.app",
            count=3,
            reviews_fn=lambda app_id, count: (fake_reviews, None),
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["url"], "googleplay_com.example.app")
        self.assertEqual(rows[0]["source"], "googleplay")

    def test_extract_steam_url_key_and_cap(self):
        fake_steam = {
            "success": 1,
            "cursor": "next_cursor",
            "reviews": [
                {
                    "review": f"fun game {i}",
                    "timestamp_created": 1700000000 + i,
                    "author": {"steamid": f"s{i}"},
                }
                for i in range(5)
            ],
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_steam
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp

        rows = scraper.extract_steam("730", total_reviews=2, session=mock_session)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["url"], "steam_730")
        self.assertEqual(rows[0]["source"], "steam")

    def test_run_scraper_deduplicates_and_formats_schema(self):
        fake_rows = [
            {
                "url": "steam_730",
                "author": "s1",
                "Text": "duplicate text",
                "date": "2025-01-01 00:00:00",
                "source": "steam",
            },
            {
                "url": "steam_730",
                "author": "s2",
                "Text": "duplicate text",
                "date": "2025-01-02 00:00:00",
                "source": "steam",
            },
            {
                "url": "steam_730",
                "author": "s3",
                "Text": "unique text",
                "date": "2025-01-03 00:00:00",
                "source": "steam",
            },
        ]
        targets = [
            {
                "category": "cs2",
                "source": "steam",
                "target": "730",
                "max_reviews": 10,
            }
        ]
        df = scraper.run_scraper(
            targets,
            rate_limit_sec=0,
            extractors={"steam": lambda key, limit: fake_rows},
        )
        self.assertEqual(list(df.columns), scraper.CHECKPOINT1_COLUMNS)
        self.assertEqual(len(df), 2)
        self.assertEqual(df.iloc[0]["category"], "cs2")
        self.assertEqual(df.iloc[0]["domain"], "gaming")
        self.assertEqual(df.iloc[0]["date"], "2025-01-01T00:00:00Z")
        self.assertEqual(df.iloc[0]["parsed_date"], "2025-01-01T00:00:00Z")

    def test_run_scraper_multi_platform_date_normalization(self):
        """Verify multi-platform extraction normalizes dates to ISO 8601 UTC and eliminates defect strings."""
        ref = datetime(2026, 10, 22, 12, 0, 0, tzinfo=scraper.timezone.utc)
        fake_rows = {
            "youtube": [
                {"url": "yt1", "author": "u1", "Text": "yt comment 1", "date": "3 months ago", "source": "youtube"},
                {"url": "yt1", "author": "u2", "Text": "yt comment 2", "date": "3 months ago (edited)", "source": "youtube"},
            ],
            "reddit": [
                {"url": "rd1", "author": "r1", "Text": "reddit comment 1", "date": "1770694597.0", "source": "reddit"},
                {"url": "rd1", "author": "r2", "Text": "reddit comment 2", "date": 1770694597.0, "source": "reddit"},
            ],
            "steam": [
                {"url": "steam_730", "author": "s1", "Text": "steam review", "date": 1710000000, "source": "steam"},
            ],
            "googleplay": [
                {"url": "googleplay_app", "author": "g1", "Text": "gp review", "date": datetime(2026, 4, 27, 17, 18, 4), "source": "googleplay"},
            ],
        }
        targets = [
            {"category": "cat_yt", "source": "youtube", "target": "yt1", "max_reviews": 5},
            {"category": "cat_rd", "source": "reddit", "target": "rd1", "max_reviews": 5},
            {"category": "cat_st", "source": "steam", "target": "730", "max_reviews": 5},
            {"category": "cat_gp", "source": "googleplay", "target": "app", "max_reviews": 5},
        ]
        df = scraper.run_scraper(
            targets,
            rate_limit_sec=0,
            scraped_date=ref,
            extractors={
                "youtube": lambda k, l: fake_rows["youtube"],
                "reddit": lambda k, l: fake_rows["reddit"],
                "steam": lambda k, l: fake_rows["steam"],
                "googleplay": lambda k, l: fake_rows["googleplay"],
            },
        )
        self.assertEqual(len(df), 6)
        self.assertEqual(list(df.columns), scraper.CHECKPOINT1_COLUMNS)

        # 1. Assert no defect strings exist in date or parsed_date
        for col in ["date", "parsed_date"]:
            col_vals = df[col].astype(str).tolist()
            self.assertFalse(any("3 months ago" in v for v in col_vals), f"Defect string '3 months ago' found in {col}")
            self.assertFalse(any("1770694597.0" in v for v in col_vals), f"Defect float string '1770694597.0' found in {col}")
            self.assertTrue(all(v.endswith("Z") for v in col_vals), f"Non-UTC/ISO string found in {col}")

        # 2. Assert pandas and Power BI can parse every date without error
        parsed_dates = pd.to_datetime(df["date"], errors="raise", utc=True)
        self.assertEqual(len(parsed_dates), 6)
        self.assertFalse(parsed_dates.isna().any())

        parsed_parsed_dates = pd.to_datetime(df["parsed_date"], errors="raise", utc=True)
        self.assertEqual(len(parsed_parsed_dates), 6)
        self.assertFalse(parsed_parsed_dates.isna().any())

    def test_save_output_local_and_s3(self):
        df = pd.DataFrame(
            [
                {
                    "url": "googleplay_com.test",
                    "author": "alice",
                    "Text": "nice",
                    "date": "2025-01-01 00:00:00",
                    "source": "googleplay",
                    "category": "test_app",
                    "parsed_date": "2025-01-01 00:00:00",
                    "domain": "apps",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            local_csv = os.path.join(tmpdir, "Checkpoint1.csv")
            dest = scraper.save_output(
                df, output_path=local_csv, s3_bucket="", s3_key="", run_id="run1"
            )
            self.assertEqual(dest, str(Path(local_csv).resolve()))
            loaded = pd.read_csv(local_csv)
            self.assertEqual(list(loaded.columns), scraper.CHECKPOINT1_COLUMNS)
            self.assertEqual(len(loaded), 1)

        mock_s3 = MagicMock()
        s3_dest = scraper.save_output(
            df,
            output_path="Checkpoint1.csv",
            s3_bucket="my-bucket",
            s3_key="",
            run_id="20250101T000000Z",
            s3_client=mock_s3,
        )
        self.assertEqual(
            s3_dest, "s3://my-bucket/raw/run_id=20250101T000000Z/Checkpoint1.csv"
        )
        mock_s3.put_object.assert_called_once()


if __name__ == "__main__":
    unittest.main()
