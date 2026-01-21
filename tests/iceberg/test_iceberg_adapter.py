from tablesleuth.services.formats.iceberg import IcebergAdapter


def test_adapter_instantiates() -> None:
    adapter = IcebergAdapter(default_catalog="local")
    assert adapter is not None
