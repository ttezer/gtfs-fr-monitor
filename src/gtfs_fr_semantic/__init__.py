"""Independent semantic diff engine for GTFS feeds (notes/semantic/).

Input: two GTFS ZIP files. Output: canonical JSON. No dependency on gtfs_fr_pipeline internals
except the shared canonical serializer, so the package can move elsewhere later.
"""

ENGINE_VERSION = "0.7.1"
