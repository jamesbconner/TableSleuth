"""Tests for FileDiscoveryService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from tablesleuth.models.file_ref import FileRef
from tablesleuth.services.file_discovery import FileDiscoveryService


@pytest.fixture
def discovery_service() -> FileDiscoveryService:
    """Create a FileDiscoveryService instance."""
    return FileDiscoveryService()


@pytest.fixture
def test_parquet_file(nested_parquet_file: Path) -> Path:
    """Get path to test Parquet file."""
    return nested_parquet_file


def test_service_initialization() -> None:
    """Test that FileDiscoveryService can be initialized."""
    service = FileDiscoveryService()
    assert service is not None


def test_service_initialization_with_adapter() -> None:
    """Test that FileDiscoveryService can be initialized with adapter."""
    mock_adapter = Mock()
    service = FileDiscoveryService(iceberg_adapter=mock_adapter)
    assert service is not None
    assert service._iceberg_adapter == mock_adapter


def test_discover_from_path_single_file(
    discovery_service: FileDiscoveryService,
    test_parquet_file: Path,
) -> None:
    """Test discovering a single Parquet file."""
    files = discovery_service.discover_from_path(test_parquet_file)

    assert len(files) == 1
    assert files[0].path == str(test_parquet_file)
    assert files[0].source == "direct"
    assert files[0].file_size_bytes > 0


def test_discover_from_path_with_string(
    discovery_service: FileDiscoveryService,
    test_parquet_file: Path,
) -> None:
    """Test discovering with string path."""
    files = discovery_service.discover_from_path(str(test_parquet_file))

    assert len(files) == 1
    assert files[0].path == str(test_parquet_file)


def test_discover_from_path_nonexistent_file(
    discovery_service: FileDiscoveryService,
) -> None:
    """Test that nonexistent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="not found"):
        discovery_service.discover_from_path("nonexistent.parquet")


def test_discover_from_path_invalid_file(
    discovery_service: FileDiscoveryService,
    tmp_path: Path,
) -> None:
    """Test that non-Parquet file raises ValueError."""
    # Create a non-Parquet file
    invalid_file = tmp_path / "invalid.parquet"
    invalid_file.write_text("not a parquet file")

    with pytest.raises(ValueError, match="not a Parquet file"):
        discovery_service.discover_from_path(invalid_file)


def test_discover_from_path_directory(
    discovery_service: FileDiscoveryService,
    multi_file_directory: Path,
) -> None:
    """Test discovering files from directory."""
    files = discovery_service.discover_from_path(multi_file_directory)

    # Should find at least one Parquet file
    assert len(files) > 0

    # All files should be from directory source
    for file_ref in files:
        assert file_ref.source == "directory"
        assert file_ref.file_size_bytes > 0


def test_discover_from_path_empty_directory(
    discovery_service: FileDiscoveryService,
    tmp_path: Path,
) -> None:
    """Test discovering from empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    files = discovery_service.discover_from_path(empty_dir)

    # Should return empty list
    assert len(files) == 0


def test_is_parquet_file_valid(
    discovery_service: FileDiscoveryService,
    test_parquet_file: Path,
) -> None:
    """Test that valid Parquet file is recognized."""
    assert discovery_service._is_parquet_file(test_parquet_file) is True


def test_is_parquet_file_invalid_extension(
    discovery_service: FileDiscoveryService,
    tmp_path: Path,
) -> None:
    """Test that file with wrong extension is rejected."""
    invalid_file = tmp_path / "file.txt"
    invalid_file.write_text("test")

    assert discovery_service._is_parquet_file(invalid_file) is False


def test_is_parquet_file_invalid_content(
    discovery_service: FileDiscoveryService,
    tmp_path: Path,
) -> None:
    """Test that file with .parquet extension but invalid content is rejected."""
    invalid_file = tmp_path / "invalid.parquet"
    invalid_file.write_text("not a parquet file")

    assert discovery_service._is_parquet_file(invalid_file) is False


def test_scan_directory_recursive(
    discovery_service: FileDiscoveryService,
    tmp_path: Path,
    test_parquet_file: Path,
) -> None:
    """Test that directory scanning is recursive."""
    # Create nested directory structure
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    # Copy test file to subdirectory
    import shutil

    dest_file = subdir / "test.parquet"
    shutil.copy(test_parquet_file, dest_file)

    # Scan parent directory
    files = discovery_service._scan_directory(tmp_path)

    # Should find file in subdirectory
    assert len(files) >= 1
    assert any(str(f).endswith("test.parquet") for f in files)


def test_scan_directory_sorted(
    discovery_service: FileDiscoveryService,
    tmp_path: Path,
    test_parquet_file: Path,
) -> None:
    """Test that scan results are sorted."""
    import shutil

    # Create multiple files
    file1 = tmp_path / "b.parquet"
    file2 = tmp_path / "a.parquet"
    shutil.copy(test_parquet_file, file1)
    shutil.copy(test_parquet_file, file2)

    files = discovery_service._scan_directory(tmp_path)

    # Should be sorted
    assert len(files) == 2
    assert str(files[0]).endswith("a.parquet")
    assert str(files[1]).endswith("b.parquet")


def test_create_file_ref(
    discovery_service: FileDiscoveryService,
    test_parquet_file: Path,
) -> None:
    """Test creating FileRef from path."""
    file_ref = discovery_service._create_file_ref(test_parquet_file, "test")

    assert file_ref.path == str(test_parquet_file)
    assert file_ref.source == "test"
    assert file_ref.file_size_bytes > 0
    # Record count may or may not be available
    assert file_ref.record_count is None or file_ref.record_count > 0


def test_discover_from_table_without_adapter(
    discovery_service: FileDiscoveryService,
) -> None:
    """Test that discover_from_table raises error without adapter."""
    with pytest.raises(ValueError, match="not configured"):
        discovery_service.discover_from_table("db.table", "catalog")


def test_discover_from_table_with_adapter() -> None:
    """Test discovering from table with adapter."""
    # Create mock adapter
    mock_adapter = Mock()
    mock_files = [
        FileRef(
            path="/path/to/file1.parquet",
            file_size_bytes=1024,
            record_count=100,
            source="iceberg",
        ),
        FileRef(
            path="/path/to/file2.parquet",
            file_size_bytes=2048,
            record_count=200,
            source="iceberg",
        ),
    ]
    mock_adapter.get_data_files.return_value = mock_files

    # Create service with adapter
    service = FileDiscoveryService(iceberg_adapter=mock_adapter)

    # Discover files
    files = service.discover_from_table("db.table", "catalog")

    # Verify
    assert len(files) == 2
    assert files[0].path == "/path/to/file1.parquet"
    assert files[1].path == "/path/to/file2.parquet"

    # Verify adapter was called correctly
    mock_adapter.get_data_files.assert_called_once_with("db.table", "catalog")


def test_discover_from_table_adapter_error() -> None:
    """Test that adapter errors are propagated."""
    # Create mock adapter that raises error
    mock_adapter = Mock()
    mock_adapter.get_data_files.side_effect = Exception("Catalog error")

    # Create service with adapter
    service = FileDiscoveryService(iceberg_adapter=mock_adapter)

    # Should raise exception
    with pytest.raises(Exception, match="Catalog error"):
        service.discover_from_table("db.table", "catalog")


def test_valid_extensions() -> None:
    """Test that service recognizes valid Parquet extensions."""
    service = FileDiscoveryService()

    assert ".parquet" in service._valid_extensions
    assert ".pq" in service._valid_extensions


def test_file_ref_has_record_count(
    discovery_service: FileDiscoveryService,
    test_parquet_file: Path,
) -> None:
    """Test that FileRef includes record count when available."""
    files = discovery_service.discover_from_path(test_parquet_file)

    assert len(files) == 1
    # Record count should be extracted from Parquet metadata
    assert files[0].record_count is not None
    assert files[0].record_count > 0
