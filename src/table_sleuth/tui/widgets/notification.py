"""Notification widget for displaying messages to users."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.timer import Timer
from textual.widgets import Static


class Notification(Container):
    """Widget for displaying temporary notifications.

    Supports different notification types:
    - info: Informational messages (blue)
    - success: Success messages (green)
    - warning: Warning messages (yellow)
    - error: Error messages (red)
    """

    DEFAULT_CSS = """
    Notification {
        dock: top;
        height: auto;
        padding: 0 1;
        display: none;
    }

    Notification.visible {
        display: block;
    }

    Notification.info {
        background: $accent;
        color: $text;
    }

    Notification.success {
        background: $success;
        color: $text;
    }

    Notification.warning {
        background: $warning;
        color: $text;
    }

    Notification.error {
        background: $error;
        color: $text;
    }

    Notification > Static {
        width: 100%;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the notification widget.

        Args:
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._message_widget: Static | None = None
        self._auto_dismiss_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        """Compose the notification widget."""
        yield Static("", id="notification-message")

    def on_mount(self) -> None:
        """Set up the widget when mounted."""
        self._message_widget = self.query_one("#notification-message", Static)

    def show(
        self,
        message: str,
        notification_type: str = "info",
        duration: float = 5.0,
    ) -> None:
        """Show a notification message.

        Args:
            message: Message to display
            notification_type: Type of notification (info, success, warning, error)
            duration: Duration in seconds (0 = no auto-dismiss)
        """
        if self._message_widget is None:
            return

        # Update message
        self._message_widget.update(message)

        # Remove old type classes
        self.remove_class("info", "success", "warning", "error")

        # Add new type class
        self.add_class(notification_type)

        # Show notification
        self.add_class("visible")

        # Cancel existing timer
        if self._auto_dismiss_timer is not None:
            self._auto_dismiss_timer.stop()
            self._auto_dismiss_timer = None

        # Set auto-dismiss timer if duration > 0
        if duration > 0:
            self._auto_dismiss_timer = self.set_timer(duration, self.dismiss)

    def dismiss(self) -> None:
        """Dismiss the notification."""
        self.remove_class("visible")

        # Cancel timer if active
        if self._auto_dismiss_timer is not None:
            self._auto_dismiss_timer.stop()
            self._auto_dismiss_timer = None

    def info(self, message: str, duration: float = 5.0) -> None:
        """Show an info notification.

        Args:
            message: Message to display
            duration: Duration in seconds
        """
        self.show(message, "info", duration)

    def success(self, message: str, duration: float = 5.0) -> None:
        """Show a success notification.

        Args:
            message: Message to display
            duration: Duration in seconds
        """
        self.show(message, "success", duration)

    def warning(self, message: str, duration: float = 5.0) -> None:
        """Show a warning notification.

        Args:
            message: Message to display
            duration: Duration in seconds
        """
        self.show(message, "warning", duration)

    def error(self, message: str, duration: float = 10.0) -> None:
        """Show an error notification.

        Args:
            message: Message to display
            duration: Duration in seconds (longer default for errors)
        """
        self.show(message, "error", duration)
