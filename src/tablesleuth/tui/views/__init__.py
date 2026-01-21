"""TUI view components for Table Sleuth."""

from .data_sample_view import DataSampleView
from .delta_view import DeltaView
from .file_detail_view import FileDetailView
from .file_list_view import FileListView
from .iceberg_view import IcebergView, SnapshotListView
from .profile_view import ProfileView
from .row_groups_view import RowGroupsView
from .schema_view import SchemaView
from .structure_view import StructureView

__all__ = [
    "FileListView",
    "FileDetailView",
    "SchemaView",
    "RowGroupsView",
    "DataSampleView",
    "ProfileView",
    "StructureView",
    "IcebergView",
    "SnapshotListView",
    "DeltaView",
]
