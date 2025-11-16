"""TUI view components for Table Sleuth."""

from .column_stats_view import ColumnStatsView
from .file_detail_view import FileDetailView
from .file_list_view import FileListView
from .profile_view import ProfileView
from .row_groups_view import RowGroupsView
from .schema_view import SchemaView
from .structure_view import StructureView

__all__ = [
    "FileListView",
    "FileDetailView",
    "SchemaView",
    "RowGroupsView",
    "ColumnStatsView",
    "ProfileView",
    "StructureView",
]
