"""Shared thread pool for blocking Google API I/O calls.

Used by both DiscoveryService and DocumentIngestService to avoid duplicating
thread pool resources.
"""

from concurrent.futures import ThreadPoolExecutor
from app.core.config import settings

google_io_executor = ThreadPoolExecutor(
    max_workers=settings.google_io_pool_size,
    thread_name_prefix="google-io",
)
