"""
test_retriever_caching.py — Unit test for Chroma client/collection LRU caching in tutor/retriever.py.

Verifies:
1. Calls to _get_client with same path return identical client instance.
2. Calls to _get_client with different paths return distinct client instances (lecture isolation).
3. Calls to _get_collection_by_name with identical params return cached collection instance.

Run:
    venv/bin/python tutor/test_retriever_caching.py
"""

import sys
import tempfile
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from tutor.retriever import _get_client, _get_collection_by_name, NOTES_COLLECTION


def test_client_caching_same_and_different_paths():
    with tempfile.TemporaryDirectory() as dir1, tempfile.TemporaryDirectory() as dir2:
        c1_a = _get_client(dir1)
        c1_b = _get_client(dir1)
        c2 = _get_client(dir2)

        # Same path must return identical client (lru_cache hit)
        assert c1_a is c1_b, "Expected identical PersistentClient instance for same path"

        # Different path must return distinct client instance (lecture isolation)
        assert c1_a is not c2, "Expected distinct PersistentClient instances for different paths"

        print("PASS test_client_caching_same_and_different_paths")


def test_collection_caching_same_path():
    with tempfile.TemporaryDirectory() as dir1:
        client = _get_client(dir1)

        # Create dummy collection so get_collection succeeds
        client.create_collection(name=NOTES_COLLECTION)

        col_a = _get_collection_by_name(NOTES_COLLECTION, role="query", chroma_dir=dir1)
        col_b = _get_collection_by_name(NOTES_COLLECTION, role="query", chroma_dir=dir1)

        assert col_a is col_b, "Expected identical collection instance for same name and chroma_dir"

        print("PASS test_collection_caching_same_path")


if __name__ == "__main__":
    test_client_caching_same_and_different_paths()
    test_collection_caching_same_path()
    print("\nAll retriever caching tests passed.")
