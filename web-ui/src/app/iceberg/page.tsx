"use client";

import { useState } from "react";
import { IcebergTableLoader } from "@/components/iceberg/table-loader";
import { SnapshotList } from "@/components/iceberg/snapshot-list";
import { SnapshotDetail } from "@/components/iceberg/snapshot-detail";
import { DataSample } from "@/components/shared/data-sample";
import { iceberg as api } from "@/lib/api";
import type {
  IcebergSnapshotDetails,
  IcebergSnapshotInfo,
  IcebergTableInfo,
  SchemaInfo,
} from "@/lib/types";

interface TableRef {
  metadata_path?: string;
  catalog_name?: string;
  table_identifier?: string;
}

type RightTab = "details" | "forensics" | "sample";

export default function IcebergPage() {
  const [tableRef, setTableRef] = useState<TableRef | null>(null);
  const [tableInfo, setTableInfo] = useState<IcebergTableInfo | null>(null);
  const [snapshots, setSnapshots] = useState<IcebergSnapshotInfo[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [details, setDetails] = useState<IcebergSnapshotDetails | null>(null);
  const [schemas, setSchemas] = useState<SchemaInfo[]>([]);
  const [loadingSchemas, setLoadingSchemas] = useState(false);
  const [rightTab, setRightTab] = useState<RightTab>("details");
  const [loading, setLoading] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = async (ref: TableRef) => {
    setLoading(true);
    setError(null);
    setSnapshots([]);
    setSelectedId(null);
    setDetails(null);
    setSchemas([]);
    setRightTab("details");
    try {
      const [info, snaps] = await Promise.all([
        api.load(ref),
        api.snapshots(ref),
      ]);
      setTableInfo(info);
      setTableRef(ref);
      setSnapshots(snaps.snapshots);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleSelectSnapshot = async (id: string) => {
    if (!tableRef) return;
    setSelectedId(id);
    setDetails(null);
    setRightTab("details");
    setLoadingDetails(true);
    try {
      const d = await api.snapshotDetails(id, tableRef);
      setDetails(d);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleRightTab = async (tab: RightTab) => {
    setRightTab(tab);
    if (tab === "forensics" && tableRef && schemas.length === 0 && !loadingSchemas) {
      setLoadingSchemas(true);
      try {
        const res = await api.schemaEvolution(tableRef);
        setSchemas(res.schemas);
      } catch {
        // ignore — show empty state
      } finally {
        setLoadingSchemas(false);
      }
    }
  };

  const sampleFilePath = details?.data_files[0]?.file_path ?? null;

  return (
    <div className="flex flex-col h-[calc(100vh-57px)]">
      <div className="border-b p-4 bg-card">
        <h1 className="text-xl font-semibold mb-3">Iceberg Snapshot Analyzer</h1>
        <IcebergTableLoader onLoad={handleLoad} loading={loading} />
        {error && (
          <div className="mt-3 rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        {tableInfo && (
          <div className="mt-2 text-xs text-muted-foreground">
            Table UUID: {tableInfo.table_uuid} · Format v{tableInfo.format_version} ·{" "}
            {snapshots.length} snapshots
          </div>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {snapshots.length > 0 && (
          <div className="w-72 border-r overflow-auto bg-card shrink-0">
            <div className="px-4 py-2 border-b text-xs text-muted-foreground font-medium">
              {snapshots.length} snapshot{snapshots.length !== 1 ? "s" : ""}
            </div>
            <SnapshotList
              snapshots={snapshots}
              selectedId={selectedId}
              onSelect={handleSelectSnapshot}
            />
          </div>
        )}

        <div className="flex-1 overflow-hidden flex flex-col">
          {selectedId ? (
            <>
              <div className="border-b px-4 flex gap-1 bg-card shrink-0">
                {(["details", "forensics", "sample"] as RightTab[]).map((t) => (
                  <button
                    key={t}
                    onClick={() => handleRightTab(t)}
                    className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                      rightTab === t
                        ? "border-primary text-primary"
                        : "border-transparent text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {t === "details" ? "Details" : t === "forensics" ? "Forensics" : "Data Sample"}
                  </button>
                ))}
              </div>

              <div className="flex-1 overflow-auto">
                {rightTab === "details" && (
                  loadingDetails ? (
                    <div className="flex items-center justify-center h-full text-muted-foreground">
                      Loading snapshot details…
                    </div>
                  ) : details ? (
                    <SnapshotDetail details={details} />
                  ) : (
                    <div className="flex items-center justify-center h-full text-muted-foreground">
                      Loading…
                    </div>
                  )
                )}
                {rightTab === "forensics" && (
                  <div className="p-4">
                    {loadingSchemas ? (
                      <p className="text-sm text-muted-foreground">Loading schema evolution…</p>
                    ) : schemas.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No schema evolution history found.</p>
                    ) : (
                      <div className="space-y-4">
                        <h4 className="font-medium">Schema Evolution ({schemas.length} versions)</h4>
                        {schemas.map((s) => (
                          <div key={s.schema_id} className="border rounded p-3">
                            <p className="text-xs font-medium text-muted-foreground mb-2">
                              Schema ID {s.schema_id} · {s.fields.length} fields
                            </p>
                            <table className="w-full text-xs border-collapse">
                              <thead>
                                <tr className="border-b bg-muted/50">
                                  <th className="px-2 py-1 text-left">Field</th>
                                  <th className="px-2 py-1 text-left">Type</th>
                                  <th className="px-2 py-1 text-left">Required</th>
                                </tr>
                              </thead>
                              <tbody>
                                {s.fields.map((f) => (
                                  <tr key={f.field_id} className="border-b hover:bg-muted/30">
                                    <td className="px-2 py-1 font-mono">{f.name}</td>
                                    <td className="px-2 py-1 text-muted-foreground">{f.field_type}</td>
                                    <td className="px-2 py-1">{f.required ? "Yes" : "No"}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {rightTab === "sample" && (
                  <DataSample filePath={sampleFilePath} />
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              {snapshots.length > 0
                ? "Select a snapshot to inspect"
                : "Enter a metadata path or catalog info above"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
