"""Profile view widget for displaying column profiling results."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Button, Static

from table_sleuth.models.profiling import ColumnProfile


class ProfileView(Container):
    """Widget for displaying column profiling results.

    Displays profiling results from GizmoSQL backend:
    - Row count
    - Non-null count
    - Null count
    - Distinct count
    - Min/max values (for numeric and date types)

    Provides interface for triggering profiling operations.
    Shows loading indicator during profiling.
    """

    DEFAULT_CSS = """
    ProfileView {
        height: 100%;
        border: solid $primary;
        overflow-y: auto;
    }

    ProfileView > Static#profile-header {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    ProfileView > Vertical {
        height: auto;
        padding: 1;
    }

    ProfileView .profile-content {
        color: $text;
        padding: 0 1;
    }

    ProfileView .profile-loading {
        color: $accent;
        text-style: italic;
        padding: 1;
    }

    ProfileView Button {
        margin: 1;
        width: auto;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the profile view.

        Args:
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._profile_result: ColumnProfile | None = None
        self._is_loading = False

    def compose(self) -> ComposeResult:
        """Compose the profile view."""
        yield Static("Column Profile", id="profile-header")
        yield Vertical(
            Static(
                "Select a column and press 'p' to profile",
                id="profile-content",
                classes="profile-content",
            ),
            id="profile-container",
        )

    def show_loading(self, column_name: str) -> None:
        """Show loading indicator for profiling operation.

        Args:
            column_name: Name of column being profiled
        """
        self._is_loading = True

        # Update header
        header = self.query_one("#profile-header", Static)
        header.update(f"Profiling: {column_name}")

        # Show loading message
        content = self.query_one("#profile-content", Static)
        content.update("⏳ Profiling in progress...")
        content.remove_class("profile-content")
        content.add_class("profile-loading")

    def update_profile(self, profile: ColumnProfile) -> None:
        """Update the displayed profile results.

        Args:
            profile: ColumnProfile with profiling results
        """
        self._profile_result = profile
        self._is_loading = False

        # Update header
        header = self.query_one("#profile-header", Static)
        header.update(f"Column Profile: {profile.column}")

        # Build profile content
        lines = []

        # Row counts
        lines.append("[bold]Row Statistics[/bold]")
        lines.append(f"  Total Rows: {profile.row_count:,}")
        lines.append(f"  Non-Null Rows: {profile.non_null_count:,}")
        lines.append(f"  Null Rows: {profile.null_count:,}")

        # Calculate null percentage
        if profile.row_count > 0:
            null_pct = (profile.null_count / profile.row_count) * 100
            lines.append(f"  Null Percentage: {null_pct:.2f}%")

        lines.append("")

        # Distinct count
        lines.append("[bold]Cardinality[/bold]")
        if profile.distinct_count is not None:
            lines.append(f"  Distinct Values: {profile.distinct_count:,}")

            # Calculate cardinality percentage
            if profile.row_count > 0:
                cardinality_pct = (profile.distinct_count / profile.row_count) * 100
                lines.append(f"  Cardinality: {cardinality_pct:.2f}%")
        else:
            lines.append("  Distinct Values: N/A")

        lines.append("")

        # Min/max values
        lines.append("[bold]Value Range[/bold]")
        if profile.min_value is not None:
            min_str = self._format_value(profile.min_value)
            lines.append(f"  Min Value: {min_str}")
        else:
            lines.append("  Min Value: N/A")

        if profile.max_value is not None:
            max_str = self._format_value(profile.max_value)
            lines.append(f"  Max Value: {max_str}")
        else:
            lines.append("  Max Value: N/A")

        # Update content
        content = self.query_one("#profile-content", Static)
        content.update("\n".join(lines))
        content.remove_class("profile-loading")
        content.add_class("profile-content")

    def show_error(self, error_message: str) -> None:
        """Show error message when profiling fails.

        Args:
            error_message: Error message to display
        """
        self._is_loading = False

        # Update header
        header = self.query_one("#profile-header", Static)
        header.update("Column Profile - Error")

        # Show error message
        content = self.query_one("#profile-content", Static)
        content.update(f"[red]Error:[/red] {error_message}")
        content.remove_class("profile-loading")
        content.add_class("profile-content")

    def clear(self) -> None:
        """Clear the profile view."""
        self._profile_result = None
        self._is_loading = False

        # Update header
        header = self.query_one("#profile-header", Static)
        header.update("Column Profile")

        # Clear content
        content = self.query_one("#profile-content", Static)
        content.update("Select a column and press 'p' to profile")
        content.remove_class("profile-loading")
        content.add_class("profile-content")

    @property
    def is_loading(self) -> bool:
        """Check if profiling is in progress.

        Returns:
            True if profiling is in progress
        """
        return self._is_loading

    @staticmethod
    def _format_value(value: object) -> str:
        """Format a value for display.

        Truncates long values and handles special types.

        Args:
            value: Value to format

        Returns:
            Formatted string representation
        """
        # Convert to string
        value_str = str(value)

        # Truncate if too long
        max_length = 50
        if len(value_str) > max_length:
            return value_str[:max_length] + "..."

        return value_str
