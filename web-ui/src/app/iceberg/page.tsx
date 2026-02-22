"use client";

import { useState } from "react";
import { IcebergTableLoader } from "@/components/iceberg/table-loader";
import { SnapshotList } from "@/components/iceberg/snapshot-list";
import { SnapshotDetail } from "@/components/iceberg/snapshot-detail";
import { iceberg as api } from "@/lib/api";
import type { IcebergSnapshotDetails, IcebergSnapshotInfo, IcebergTableInfo } from "@/lib/types";

interface TableRef {
  metadata_path?: string;
  catalog_name?: string;
  table_identifier?: string;
}

export default function IcebergPage() {
  const [tableRef, setTableRef] = useState<TableRef | null>(null);
  const [tableInfo, setTableInfo] = useState<IcebergTableInfo | null>(null);
  const [snapshots, setSnapshots] = useState<IcebergSnapshotInfo[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [details, setDetails] = useState<IcebergSnapshotDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = async (ref: TableRef) => {
    setLoading(true);
    setError(null);
    setSnapshots([]);
    setSelectedId(null);
    setDetails(null);
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

  const handleSelectSnapshot = async (id: number) => {
    if (!tableRef) return;
    setSelectedId(id);
    setDetails(null);
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

        <div className="flex-1 overflow-auto">
          {loadingDetails ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Loading snapshot details...
            </div>
          ) : details ? (
            <SnapshotDetail details={details} />
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
