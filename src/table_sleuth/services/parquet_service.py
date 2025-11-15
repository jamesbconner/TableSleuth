from __future__ import annotations

from pyarrow.parquet import ParquetFile

from table_sleuth.models import ColumnStats, ParquetFileInfo


def inspect_parquet_file(path: str) -> ParquetFileInfo:
    pf = ParquetFile(path)
    md = pf.metadata
    schema = pf.schema_arrow

    row_group_sizes = [md.row_group(i).num_rows for i in range(md.num_row_groups)]
    columns: list[ColumnStats] = []

    for col_idx in range(md.num_columns):
        col_schema = md.schema.column(col_idx)
        col_name = col_schema.name
        field = schema.field(col_name)
        row_group_cols = [md.row_group(rg).column(col_idx) for rg in range(md.num_row_groups)]

        null_count = sum(c.num_nulls for c in row_group_cols)
        physical_type = col_schema.physical_type.name
        logical_type = str(field.type)

        mins = [
            c.statistics.min
            for c in row_group_cols
            if c.statistics is not None and c.statistics.has_min_max
        ]
        maxs = [
            c.statistics.max
            for c in row_group_cols
            if c.statistics is not None and c.statistics.has_min_max
        ]

        compression = row_group_cols[0].compression
        encodings = list({enc.name for c in row_group_cols for enc in (c.encodings or [])})

        columns.append(
            ColumnStats(
                name=col_name,
                physical_type=physical_type,
                logical_type=logical_type,
                null_count=null_count,
                min_value=min(mins) if mins else None,
                max_value=max(maxs) if maxs else None,
                encodings=encodings,
                compression=compression.name if hasattr(compression, "name") else str(compression),
            )
        )

    return ParquetFileInfo(
        path=path,
        num_rows=md.num_rows,
        num_row_groups=md.num_row_groups,
        row_group_sizes=row_group_sizes,
        columns=columns,
    )
