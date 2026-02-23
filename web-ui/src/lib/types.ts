/**
 * TypeScript interfaces mirroring Python dataclasses in src/tablesleuth/models/.
 */

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

export interface FileRef {
  path: string;
  file_size_bytes: number;
  record_count: number | null;
  source: string;
  content_type: string;
  partition: Record<string, unknown>;
  sequence_number: number | null;
  data_sequence_number: number | null;
  extra: Record<string, unknown>;
}

export interface SnapshotInfo {
  snapshot_id: number;
  parent_id: number | null;
  timestamp_ms: number;
  operation: string;
  summary: Record<string, string>;
  data_files: FileRef[];
  delete_files: FileRef[];
}

// ---------------------------------------------------------------------------
// Parquet
// ---------------------------------------------------------------------------

export interface ColumnStats {
  name: string;
  physical_type: string;
  logical_type: string | null;
  null_count: number | null;
  min_value: unknown;
  max_value: unknown;
  encodings: string[];
  compression: string;
  num_values: number | null;
  distinct_count: number | null;
  total_compressed_size: number | null;
  total_uncompressed_size: number | null;
}

export interface RowGroupInfo {
  index: number;
  num_rows: number;
  total_byte_size: number;
  columns: ColumnStats[];
}

export interface ParquetFileInfo {
  path: string;
  file_size_bytes: number;
  num_rows: number;
  num_row_groups: number;
  num_columns: number;
  schema: Record<string, { type: string; nullable: boolean }>;
  row_groups: RowGroupInfo[];
  columns: ColumnStats[];
  created_by: string | null;
  format_version: string;
}

export interface AnalyzeResponse {
  files: FileRef[];
  count: number;
}

export interface SampleResponse {
  columns: string[];
  rows: unknown[][];
  total_rows_in_file: number;
  sampled_rows: number;
}

// ---------------------------------------------------------------------------
// Iceberg
// ---------------------------------------------------------------------------

export interface IcebergTableInfo {
  metadata_location: string;
  format_version: number;
  table_uuid: string;
  location: string;
  // Serialized as string by the API to avoid JS float64 precision loss (int64 > 2^53).
  current_snapshot_id: string | null;
  properties: Record<string, string>;
}

export interface IcebergSnapshotInfo {
  // Serialized as strings by the API to avoid JS float64 precision loss (int64 > 2^53).
  snapshot_id: string;
  parent_snapshot_id: string | null;
  timestamp_ms: number;
  operation: string;
  summary: Record<string, string>;
  manifest_list: string;
  schema_id: number;
  total_records: number;
  total_data_files: number;
  total_delete_files: number;
  total_size_bytes: number;
  position_deletes: number;
  equality_deletes: number;
  has_deletes: boolean;
  delete_ratio: number;
  read_amplification: number;
}

export interface SchemaField {
  field_id: number;
  name: string;
  field_type: string;
  required: boolean;
  doc: string | null;
}

export interface SchemaInfo {
  schema_id: number;
  fields: SchemaField[];
}

export interface PartitionField {
  field_id: number;
  source_id: number;
  name: string;
  transform: string;
}

export interface PartitionSpecInfo {
  spec_id: number;
  fields: PartitionField[];
}

export interface SortField {
  source_id: number;
  transform: string;
  direction: string;
  null_order: string;
}

export interface SortOrderInfo {
  order_id: number;
  fields: SortField[];
}

export interface IcebergSnapshotDetails {
  snapshot_info: IcebergSnapshotInfo;
  data_files: Array<{
    file_path: string;
    file_size_bytes: number;
    record_count: number | null;
  }>;
  delete_files: Array<{
    file_path: string;
    file_size_bytes: number;
    record_count: number | null;
    content: string;
  }>;
  schema: SchemaInfo;
  partition_spec: PartitionSpecInfo;
  sort_order: SortOrderInfo | null;
}

export interface SnapshotComparison {
  snapshot_a: IcebergSnapshotInfo;
  snapshot_b: IcebergSnapshotInfo;
  data_files_added: number;
  data_files_removed: number;
  delete_files_added: number;
  delete_files_removed: number;
  records_added: number;
  records_deleted: number;
  records_delta: number;
  size_added_bytes: number;
  size_removed_bytes: number;
  size_delta_bytes: number;
  delete_ratio_change: number;
  read_amplification_change: number;
}

// ---------------------------------------------------------------------------
// Delta
// ---------------------------------------------------------------------------

export interface DeltaSchemaField {
  name: string;
  type: string;
  nullable: boolean;
}

export interface DeltaSchemaResponse {
  fields: DeltaSchemaField[];
  count: number;
}

export interface DeltaLoadResponse extends SnapshotInfo {
  current_version: number;
}

export interface DeltaVersionsResponse {
  versions: SnapshotInfo[];
  count: number;
  current_version: number;
}

export interface StorageWaste {
  active_files: { count: number; total_size_bytes: number };
  tombstone_files: { count: number; total_size_bytes: number };
  waste_percentage: number;
  reclaimable_bytes: number;
  retention_period_hours: number;
  total_storage_bytes: number;
}

export interface FileSizeAnalysis {
  histogram: Record<string, number>;
  small_file_count: number;
  small_file_percentage: number;
  optimization_opportunity: number;
  min_size_bytes: number;
  max_size_bytes: number;
  median_size_bytes: number;
  total_size_bytes: number;
  total_file_count: number;
}

export interface CheckpointHealth {
  last_checkpoint_version: number | null;
  log_tail_length: number;
  checkpoint_age_hours: number | null;
  checkpoint_file_size_bytes: number | null;
  health_status: "healthy" | "degraded" | "critical";
  issues: string[];
  recommendation: string | null;
}

export interface Recommendation {
  type: "OPTIMIZE" | "VACUUM" | "ZORDER" | "CHECKPOINT";
  priority: "high" | "medium" | "low";
  reason: string;
  estimated_impact: string;
  command: string;
  details?: Record<string, unknown>;
}

export interface DeltaForensicsResponse {
  path: string;
  current_version: number;
  file_size_analysis: FileSizeAnalysis;
  storage_waste: StorageWaste;
  checkpoint_health: CheckpointHealth;
  recommendations: Recommendation[];
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export interface AppConfig {
  catalog: { default: string | null };
  gizmosql: {
    uri: string;
    username: string;
    password: string;
    tls_skip_verify: boolean;
  };
}

export interface ConfigStatus {
  config_file: string | null;
  env_overrides: Record<string, boolean>;
  pyiceberg_yaml_exists: boolean;
  pyiceberg_yaml_path: string;
}

// ---------------------------------------------------------------------------
// GizmoSQL
// ---------------------------------------------------------------------------

export interface QueryPerformanceMetrics {
  execution_time_ms: number;
  /** Total files scanned (data + delete). */
  files_scanned: number;
  bytes_scanned: number;
  /** Total physical rows read (data-file records + delete records). */
  rows_scanned: number;
  rows_returned: number;
  memory_peak_mb: number;
  scan_efficiency: number;
  // Per-type breakdowns (populated for Iceberg MOR snapshots; 0 otherwise)
  data_files_scanned: number;
  delete_files_scanned: number;
  data_rows_scanned: number;
  delete_rows_scanned: number;
}

export interface PerformanceComparison {
  query: string;
  table_a_name: string;
  table_b_name: string;
  metrics_a: QueryPerformanceMetrics;
  metrics_b: QueryPerformanceMetrics;
  execution_time_delta_pct: number;
  files_scanned_delta_pct: number;
  analysis: string;
}

export interface GizmoStatus {
  connected: boolean;
  version?: string;
  error?: string;
}

export interface QueryResult {
  columns: string[];
  rows: unknown[][];
  row_count: number;
  elapsed_ms: number;
}

export interface ColumnProfile {
  column: string;
  row_count: number;
  non_null_count: number;
  null_count: number;
  distinct_count: number | null;
  min_value: unknown;
  max_value: unknown;
  is_numeric: boolean;
  average: number | null;
  median: number | null;
  mode: unknown;
  mode_count: number | null;
  std_dev: number | null;
  variance: number | null;
  q1: number | null;
  q3: number | null;
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  version: string;
}
