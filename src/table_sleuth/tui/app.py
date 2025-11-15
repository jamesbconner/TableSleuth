from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static

from table_sleuth.config import AppConfig
from table_sleuth.models import TableHandle
from table_sleuth.services.formats.base import TableFormatAdapter


class TableSleuthApp(App):
    """Very basic Textual app stub for Table Sleuth."""

    CSS_PATH = None

    def __init__(
        self,
        table_handle: TableHandle,
        adapter: TableFormatAdapter,
        config: AppConfig,
    ) -> None:
        super().__init__()
        self.table_handle = table_handle
        self.adapter = adapter
        self.config = config

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"Table format: {self.table_handle.format_name}", id="table-info")
        yield Footer()
