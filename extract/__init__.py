"""
extract — knowledge-extraction pipeline stage.

The previous content of this module was a stale duplicate of
extract/extractor.py (with a hardcoded deprecated model name) and was never
used — every pipeline caller imports from extract.extractor directly.
"""

from extract.extractor import (
    extract_all_chunks,
    process_chunk,
    process_chunk_with_retry,
)
