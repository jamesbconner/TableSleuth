"""Loading indicator widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static


class LoadingIndicator(Container):
    """Widget for displaying loading status.

    Shows a loading message with an animated indicator.
    """

    DEFAULT_CSS = """
    LoadingIndicator {
        dock: top;
        height: auto;
        padding: 0 1;
        background: $accent;
        color: $text;
        display: none;
    }

    LoadingIndicator.visible {
        display: block;
    }

    LoadingIndicator > Static {
        width: 100%;
        text-style: italic;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the loading indicator.

        Args:
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._message_widget: Static | None = None

    def compose(self) -> ComposeResult:
        """Compose the loading indicator."""
        yield Static("", id="loading-message")

    def on_mount(self) -> None:
        """Set up the widget when mounted."""
        self._message_widget = self.query_one("#loading-message", Static)

    def show(self, message: str = "Loading...") -> None:
        """Show the loading indicator.

        Args:
            message: Loading message to display
        """
        if self._message_widget is None:
            return

        # Update message with loading indicator
        self._message_widget.update(f"⏳ {message}")

        # Show indicator
        self.add_class("visible")

    def hide(self) -> None:
        """Hide the loading indicator."""
        self.remove_class("visible")
