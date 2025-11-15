from table_sleuth.config import AppConfig, CatalogConfig, GizmoConfig
from table_sleuth.models import TableHandle
from table_sleuth.services.formats.iceberg import IcebergAdapter
from table_sleuth.tui.app import TableSleuthApp


def test_tui_smoke() -> None:
    dummy_table = TableHandle(native=None, format_name="iceberg")
    adapter = IcebergAdapter(default_catalog=None)
    config = AppConfig(catalog=CatalogConfig(default=None), gizmosql=GizmoConfig())
    app = TableSleuthApp(table_handle=dummy_table, adapter=adapter, config=config)
    assert app is not None
