"""
Update metadata for existing assets with calculated totals.
Run: python -m storage.update_metadata
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.database import get_db_connection, db_transaction
from storage.models import Asset

# Paths
BASE_DIR = Path(__file__).parent.parent
SCRAPE_HISTORY_FILE = BASE_DIR / 'scrape_history.json'


def update_skeleton_assets():
    """Update skeleton/skeleton_report assets with calculated totals."""
    print("\n--- Updating Skeleton Assets ---")

    # Get all skeleton-type assets
    assets = Asset.list(type='skeleton') + Asset.list(type='skeleton_report')
    updated = 0

    for asset in assets:
        content_path = asset.content_path
        if not content_path:
            continue

        content_dir = Path(content_path)
        skeletons_json = content_dir / 'skeletons.json'

        if not skeletons_json.exists():
            print(f"  Skipping {asset.id}: no skeletons.json")
            continue

        try:
            with open(skeletons_json, 'r', encoding='utf-8') as f:
                skeletons = json.load(f)

            if not isinstance(skeletons, list):
                continue

            # Calculate totals
            total_views = 0
            total_likes = 0
            creators = []
            has_transcripts = False

            for sk in skeletons:
                # Views - try multiple locations
                views = sk.get('views', 0) or sk.get('metrics', {}).get('views', 0) or 0
                total_views += views

                # Likes
                likes = sk.get('likes', 0) or sk.get('metrics', {}).get('likes', 0) or 0
                total_likes += likes

                # Creator
                creator = sk.get('creator_username') or sk.get('creator', {}).get('handle', '')
                if creator and creator not in creators:
                    creators.append(creator)

                # Transcripts
                if sk.get('transcript'):
                    has_transcripts = True

            # Update metadata
            current_meta = asset.metadata or {}
            current_meta['total_views'] = total_views
            current_meta['total_likes'] = total_likes
            current_meta['has_transcripts'] = has_transcripts
            current_meta['video_count'] = len(skeletons)
            if creators:
                current_meta['creators'] = creators

            asset.update(metadata=current_meta)
            updated += 1
            print(f"  Updated: {asset.title[:50]}... (views: {total_views:,}, likes: {total_likes:,})")

        except Exception as e:
            print(f"  Error updating {asset.id}: {e}")

    print(f"  Total updated: {updated}")
    return updated


def update_scrape_assets():
    """Update scrape/scrape_report assets with calculated totals."""
    print("\n--- Updating Scrape Assets ---")

    # Load scrape history
    if not SCRAPE_HISTORY_FILE.exists():
        print(f"  No scrape_history.json found")
        return 0

    try:
        with open(SCRAPE_HISTORY_FILE, 'r') as f:
            history = json.load(f)
    except Exception as e:
        print(f"  Error reading scrape_history.json: {e}")
        return 0

    # Get all scrape-type assets
    assets = Asset.list(type='scrape') + Asset.list(type='scrape_report')
    updated = 0

    for asset in assets:
        meta = asset.metadata or {}
        original_id = meta.get('original_id')
        username = meta.get('username')

        # Find matching scrape entry
        scrape_data = None
        if original_id:
            scrape_data = next((h for h in history if h.get('id') == original_id), None)
        if not scrape_data and username:
            scrape_data = next((h for h in history if h.get('username') == username), None)

        if not scrape_data:
            print(f"  Skipping {asset.id}: no matching scrape data")
            continue

        try:
            top_reels = scrape_data.get('top_reels', [])

            # Calculate totals from top_reels
            total_views = sum(r.get('views', 0) or 0 for r in top_reels)
            total_likes = sum(r.get('likes', 0) or 0 for r in top_reels)
            total_comments = sum(r.get('comments', 0) or 0 for r in top_reels)
            has_transcripts = any(r.get('transcript') for r in top_reels)

            # Update metadata
            meta['total_views'] = total_views
            meta['total_likes'] = total_likes
            meta['total_comments'] = total_comments
            meta['has_transcripts'] = has_transcripts
            meta['total_reels'] = scrape_data.get('total_reels', 0)
            meta['top_count'] = scrape_data.get('top_count', len(top_reels))

            asset.update(metadata=meta)
            updated += 1
            print(f"  Updated: @{username} (views: {total_views:,}, likes: {total_likes:,})")

        except Exception as e:
            print(f"  Error updating {asset.id}: {e}")

    print(f"  Total updated: {updated}")
    return updated


def run_update():
    """Run full metadata update."""
    print("=" * 50)
    print("ASSET METADATA UPDATE")
    print("=" * 50)

    skeletons = update_skeleton_assets()
    scrapes = update_scrape_assets()

    print("\n" + "=" * 50)
    print("UPDATE COMPLETE")
    print("=" * 50)
    print(f"  Skeleton assets updated: {skeletons}")
    print(f"  Scrape assets updated: {scrapes}")


if __name__ == '__main__':
    run_update()
