"""
Test script for storage module - validates schema and CRUD operations.
Run: python -m storage.test_storage
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.database import init_db, DATABASE_PATH
from storage.models import Asset, Collection, AssetCollection


def test_database_init():
    """Test database initialization."""
    print("Testing database initialization...")
    db_path = init_db()
    assert db_path.exists(), "Database file should exist"
    print(f"  Database created at: {db_path}")
    print("  PASS")


def test_asset_crud():
    """Test Asset create, read, update, delete."""
    print("\nTesting Asset CRUD...")

    # Create
    asset = Asset.create(
        type='skeleton',
        title='Test Skeleton Report',
        content_path='/test/path',
        preview='This is a test preview',
        metadata={'creator': 'testuser', 'video_count': 5}
    )
    print(f"  Created asset: {asset.id}")
    assert asset.id is not None

    # Read
    fetched = Asset.get(asset.id)
    assert fetched is not None
    assert fetched.title == 'Test Skeleton Report'
    print(f"  Fetched asset: {fetched.title}")

    # Update
    fetched.update(title='Updated Title', starred=True)
    refetched = Asset.get(asset.id)
    assert refetched.title == 'Updated Title'
    assert refetched.starred == True
    print(f"  Updated asset: {refetched.title}, starred={refetched.starred}")

    # List
    assets = Asset.list(type='skeleton')
    assert len(assets) >= 1
    print(f"  Listed {len(assets)} skeleton assets")

    # Search
    results = Asset.search('skeleton')
    print(f"  Search found {len(results)} results")

    # Delete
    asset.delete()
    deleted = Asset.get(asset.id)
    assert deleted is None
    print("  Deleted asset successfully")

    print("  PASS")


def test_collection_crud():
    """Test Collection create, read, update, delete."""
    print("\nTesting Collection CRUD...")

    # Create
    collection = Collection.create(
        name='Test Collection',
        description='A test collection',
        color='#ff0000'
    )
    print(f"  Created collection: {collection.id}")

    # Read
    fetched = Collection.get(collection.id)
    assert fetched is not None
    assert fetched.name == 'Test Collection'
    print(f"  Fetched collection: {fetched.name}")

    # Update
    fetched.update(name='Updated Collection')
    refetched = Collection.get(collection.id)
    assert refetched.name == 'Updated Collection'
    print(f"  Updated collection: {refetched.name}")

    # List
    collections = Collection.list()
    assert len(collections) >= 1
    print(f"  Listed {len(collections)} collections")

    # Delete
    collection.delete()
    deleted = Collection.get(collection.id)
    assert deleted is None
    print("  Deleted collection successfully")

    print("  PASS")


def test_asset_collections():
    """Test adding/removing assets to collections."""
    print("\nTesting Asset-Collection relationships...")

    # Create test data
    asset = Asset.create(type='scrape', title='Test Scrape')
    collection = Collection.create(name='My Collection')

    # Add to collection
    asset.add_to_collection(collection.id)
    asset_collections = asset.get_collections()
    assert len(asset_collections) == 1
    print(f"  Added asset to collection: {collection.name}")

    # Get assets in collection
    collection_assets = collection.get_assets()
    assert len(collection_assets) == 1
    print(f"  Collection has {len(collection_assets)} asset(s)")

    # Asset count
    count = collection.asset_count()
    assert count == 1
    print(f"  Collection asset count: {count}")

    # Remove from collection
    asset.remove_from_collection(collection.id)
    asset_collections = asset.get_collections()
    assert len(asset_collections) == 0
    print("  Removed asset from collection")

    # Cleanup
    asset.delete()
    collection.delete()

    print("  PASS")


def run_all_tests():
    """Run all tests."""
    print("=" * 50)
    print("STORAGE MODULE TESTS")
    print("=" * 50)

    test_database_init()
    test_asset_crud()
    test_collection_crud()
    test_asset_collections()

    print("\n" + "=" * 50)
    print("ALL TESTS PASSED")
    print("=" * 50)


if __name__ == '__main__':
    run_all_tests()
