/**
 * API client for the TableSleuth FastAPI backend.
 *
 * All calls target /api/* (same-origin relative URLs).
 * In development, configure your Next.js rewrites or run 'make dev-api'
 * on a separate port and set NEXT_PUBLIC_API_URL accordingly.
 */

import type {
  AnalyzeResponse,
  AppConfig,
  CheckpointHealth,
  ConfigStatus,
  DeltaForensicsResponse,
  DeltaLoadResponse,
  DeltaSchemaResponse,
  DeltaVersionsResponse,
  FileSizeAnalysis,
  GizmoStatus,
  HealthResponse,
  IcebergSnapshotDetails,
  IcebergSnapshotInfo,
  IcebergTableInfo,
  ParquetFileInfo,
  QueryResult,
  SampleResponse,
  SchemaInfo,
  SnapshotComparison,
  StorageWaste,
} from "./types";

const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "") + "/api";

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try {
      const json = JSON.parse(text);
      detail = json.detail ?? text;
    } catch {
      // use raw text
    }
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }

  return res.json() as Promise<T>;
}

const get = <T>(path: string) => request<T>("GET", path);
const post = <T>(path: string, body: unknown) => request<T>("POST", path, body);
const put = <T>(path: string, body: unknown) => request<T>("PUT", path, body);

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export const health = {
  get: () => get<HealthResponse>("/health"),
};

// ---------------------------------------------------------------------------
// Parquet
// ---------------------------------------------------------------------------

export const parquet = {
  analyze: (path: string, catalog_name?: string, region?: string) =>
    post<AnalyzeResponse>("/parquet/analyze", { path, catalog_name, region }),

  fileInfo: (path: string, region?: string) =>
    post<ParquetFileInfo>("/parquet/file-info", { path, region }),

  sample: (path: string, num_rows = 100, region?: string) =>
    post<SampleResponse>("/parquet/sample", { path, num_rows, region }),
};

// ---------------------------------------------------------------------------
// Iceberg
// ---------------------------------------------------------------------------

interface IcebergRef {
  metadata_path?: string;
  catalog_name?: string;
  table_identifier?: string;
}

export const iceberg = {
  catalogs: () =>
    get<{ catalogs: string[]; path: string; exists: boolean }>("/iceberg/catalogs"),

  catalogTables: (catalog_name: string) =>
    post<{ tables: string[]; count: number; catalog: string }>(
      "/iceberg/catalog-tables",
      { catalog_name }
    ),

  load: (ref: IcebergRef) =>
    post<IcebergTableInfo>("/iceberg/load", ref),

  snapshots: (ref: IcebergRef) =>
    post<{ snapshots: IcebergSnapshotInfo[]; count: number }>(
      "/iceberg/snapshots",
      ref
    ),

  snapshotDetails: (snapshot_id: string, ref: IcebergRef) =>
    post<IcebergSnapshotDetails>(`/iceberg/snapshot/${snapshot_id}`, ref),

  compare: (
    ref: IcebergRef,
    snapshot_a_id: string,
    snapshot_b_id: string
  ) =>
    post<SnapshotComparison>("/iceberg/compare", {
      ...ref,
      snapshot_a_id,
      snapshot_b_id,
    }),

  schemaEvolution: (ref: IcebergRef) =>
    post<{ schemas: SchemaInfo[]; count: number }>(
      "/iceberg/schema-evolution",
      ref
    ),
};

// ---------------------------------------------------------------------------
// Delta
// ---------------------------------------------------------------------------

interface DeltaRef {
  path: string;
  version?: number;
  storage_options?: Record<string, string>;
}

export const delta = {
  load: (ref: DeltaRef) =>
    post<DeltaLoadResponse>("/delta/load", ref),

  versions: (ref: DeltaRef) =>
    post<DeltaVersionsResponse>("/delta/versions", ref),

  forensics: (ref: DeltaRef) =>
    post<DeltaForensicsResponse>("/delta/forensics", ref),

  schema: (ref: DeltaRef) =>
    post<DeltaSchemaResponse>("/delta/schema", ref),

  schemaEvolution: (ref: DeltaRef) =>
    post<{ evolution: unknown[]; count: number }>(
      "/delta/schema-evolution",
      ref
    ),
};

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export const config = {
  get: () => get<AppConfig>("/config/"),

  save: (cfg: Partial<AppConfig>) => put<{ saved: boolean; path: string; config: AppConfig }>("/config/", cfg),

  status: () => get<ConfigStatus>("/config/status"),

  getPyiceberg: () =>
    get<{ exists: boolean; path: string; config: Record<string, unknown> }>(
      "/config/pyiceberg"
    ),

  savePyiceberg: (cfg: Record<string, unknown>) =>
    put<{ saved: boolean; path: string }>("/config/pyiceberg", cfg),

  uploadPyiceberg: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/config/pyiceberg/upload`, { method: "POST", body: form });
    if (!res.ok) {
      const text = await res.text();
      let detail = text;
      try { detail = JSON.parse(text).detail ?? text; } catch { /* raw */ }
      throw new Error(`${res.status} ${res.statusText}: ${detail}`);
    }
    return res.json() as Promise<{ saved: boolean; path: string; config: Record<string, unknown> }>;
  },
};

// ---------------------------------------------------------------------------
// GizmoSQL
// ---------------------------------------------------------------------------

export const gizmosql = {
  status: () => get<GizmoStatus>("/gizmosql/status"),

  query: (sql: string) =>
    post<QueryResult>("/gizmosql/query", { sql }),

  profile: (
    table_ref: string,
    columns: string[],
    metadata_location?: string,
    snapshot_id?: number
  ) =>
    post<Record<string, unknown>>("/gizmosql/profile", {
      table_ref,
      columns,
      metadata_location,
      snapshot_id,
    }),
};
