"""
Migration script for existing file-based data to SQLite.
Run: python -m storage.migrate
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.database import init_db
from storage.models import Asset

# Paths
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / 'output'
SKELETON_REPORTS_DIR = OUTPUT_DIR / 'skeleton_reports'
SCRAPE_HISTORY_FILE = BASE_DIR / 'scrape_history.json'


def migrate_scrape_history():
    """Import scrapes from scrape_history.json"""
    print("\n--- Migrating Scrape History ---")

    if not SCRAPE_HISTORY_FILE.exists():
        print(f"  No scrape_history.json found at {SCRAPE_HISTORY_FILE}")
        return 0

    try:
        with open(SCRAPE_HISTORY_FILE, 'r') as f:
            history = json.load(f)
    except Exception as e:
        print(f"  Error reading scrape_history.json: {e}")
        return 0

    if not isinstance(history, list):
        print(f"  Invalid format: expected list, got {type(history)}")
        return 0

    imported = 0
    skipped = 0

    for entry in history:
        scrape_id = entry.get('id')
        if not scrape_id:
            continue

        # Check if already imported (by checking content_path or metadata)
        existing = Asset.list(type='scrape')
        already_exists = any(
            a.metadata and a.metadata.get('original_id') == scrape_id
            for a in existing
        )

        if already_exists:
            skipped += 1
            continue

        # Extract data
        username = entry.get('username', 'Unknown')
        timestamp = entry.get('timestamp', '')
        profile = entry.get('profile', {})
        top_reels = entry.get('top_reels', [])
        total_reels = entry.get('total_reels', 0)
        top_count = entry.get('top_count', 0)

        # Determine platform
        channel_url = profile.get('channel_url', '')
        platform = 'tiktok' if 'tiktok.com' in channel_url else 'instagram'

        # Build preview
        preview_parts = []
        for i, reel in enumerate(top_reels[:3], 1):
            views = reel.get('views', 0)
            caption = (reel.get('caption', '')[:80] + '...') if len(reel.get('caption', '')) > 80 else reel.get('caption', '')
            preview_parts.append(f"{i}. {views:,} views - {caption}")
        preview = '\n'.join(preview_parts) if preview_parts else 'No reels data'

        # Determine content path
        output_subdir = f"output_{username}" if platform == 'instagram' else f"output_{username}_tiktok"
        content_path = str(OUTPUT_DIR / output_subdir)

        # Create asset
        try:
            asset = Asset.create(
                type='scrape',
                title=f"@{username} - {platform.title()} Scrape ({top_count}/{total_reels} reels)",
                content_path=content_path,
                preview=preview,
                metadata={
                    'original_id': scrape_id,
                    'username': username,
                    'platform': platform,
                    'total_reels': total_reels,
                    'top_count': top_count,
                    'profile': profile,
                    'original_timestamp': timestamp
                }
            )
            imported += 1
            print(f"  Imported: @{username} ({platform})")
        except Exception as e:
            print(f"  Error importing @{username}: {e}")

    print(f"  Total: {imported} imported, {skipped} skipped (already exist)")
    return imported


def migrate_skeleton_reports():
    """Import skeleton reports from output/skeleton_reports/"""
    print("\n--- Migrating Skeleton Reports ---")

    if not SKELETON_REPORTS_DIR.exists():
        print(f"  No skeleton_reports directory found at {SKELETON_REPORTS_DIR}")
        return 0

    imported = 0
    skipped = 0

    for report_dir in SKELETON_REPORTS_DIR.iterdir():
        if not report_dir.is_dir():
            continue

        report_id = report_dir.name

        # Check if already imported
        existing = Asset.list(type='skeleton')
        already_exists = any(
            a.metadata and a.metadata.get('report_id') == report_id
            for a in existing
        )

        if already_exists:
            skipped += 1
            continue

        # Look for report.md and skeletons.json
        report_md = report_dir / 'report.md'
        skeletons_json = report_dir / 'skeletons.json'

        if not report_md.exists():
            print(f"  Skipping {report_id}: no report.md found")
            continue

        # Read report content for preview
        try:
            with open(report_md, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
            preview = markdown_content[:500] + '...' if len(markdown_content) > 500 else markdown_content
        except Exception as e:
            preview = f"Error reading report: {e}"

        # Read skeletons.json for metadata
        video_count = 0
        creators = []
        if skeletons_json.exists():
            try:
                with open(skeletons_json, 'r', encoding='utf-8') as f:
                    skeletons = json.load(f)
                video_count = len(skeletons) if isinstance(skeletons, list) else 0
                # Extract unique creators
                for sk in skeletons if isinstance(skeletons, list) else []:
                    creator = sk.get('creator', {}).get('handle', '')
                    if creator and creator not in creators:
                        creators.append(creator)
            except Exception:
                pass

        # Parse timestamp from report_id (format: YYYYMMDD_HHMMSS_sr_xxxx)
        try:
            date_part = report_id.split('_')[0]
            time_part = report_id.split('_')[1]
            created_at = datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S").isoformat()
        except Exception:
            created_at = None

        # Build title
        if creators:
            title = f"{', '.join(creators[:3])} - Skeleton Report ({video_count} videos)"
        else:
            title = f"Skeleton Report - {report_id} ({video_count} videos)"

        # Create asset
        try:
            asset = Asset.create(
                type='skeleton',
                title=title,
                content_path=str(report_dir),
                preview=preview,
                metadata={
                    'report_id': report_id,
                    'video_count': video_count,
                    'creators': creators,
                    'original_created_at': created_at
                }
            )
            imported += 1
            print(f"  Imported: {report_id}")
        except Exception as e:
            print(f"  Error importing {report_id}: {e}")

    print(f"  Total: {imported} imported, {skipped} skipped (already exist)")
    return imported


def run_migration():
    """Run full migration."""
    print("=" * 50)
    print("ASSET LIBRARY MIGRATION")
    print("=" * 50)

    # Initialize database
    print("\nInitializing database...")
    db_path = init_db()
    print(f"  Database: {db_path}")

    # Run migrations
    scrapes = migrate_scrape_history()
    skeletons = migrate_skeleton_reports()

    # Summary
    print("\n" + "=" * 50)
    print("MIGRATION COMPLETE")
    print("=" * 50)
    print(f"  Scrapes imported: {scrapes}")
    print(f"  Skeleton reports imported: {skeletons}")
    print(f"  Total assets: {scrapes + skeletons}")

    # Verify
    total = len(Asset.list())
    print(f"\n  Total assets in database: {total}")


if __name__ == '__main__':
    run_migration()
