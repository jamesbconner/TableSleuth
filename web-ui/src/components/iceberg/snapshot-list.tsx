"use client";

import { formatBytes, formatNumber, formatTimestamp } from "@/lib/utils";
import type { IcebergSnapshotInfo } from "@/lib/types";

interface SnapshotListProps {
  snapshots: IcebergSnapshotInfo[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

function operationBadge(op: string) {
  const colors: Record<string, string> = {
    APPEND: "bg-green-100 text-green-800",
    UPDATE: "bg-yellow-100 text-yellow-800",
    DELETE: "bg-red-100 text-red-800",
    REPLACE: "bg-orange-100 text-orange-800",
    OVERWRITE: "bg-purple-100 text-purple-800",
  };
  return colors[op.toUpperCase()] ?? "bg-gray-100 text-gray-700";
}

export function SnapshotList({ snapshots, selectedId, onSelect }: SnapshotListProps) {
  return (
    <div className="divide-y">
      {snapshots.map((snap) => (
        <button
          key={snap.snapshot_id}
          onClick={() => onSelect(snap.snapshot_id)}
          className={`w-full text-left px-4 py-3 hover:bg-accent transition-colors ${
            selectedId === snap.snapshot_id ? "bg-accent" : ""
          }`}
        >
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`text-xs font-medium px-1.5 py-0.5 rounded ${operationBadge(snap.operation)}`}
            >
              {snap.operation}
            </span>
            <span className="text-xs font-mono text-muted-foreground">
              #{snap.snapshot_id}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">{formatTimestamp(snap.timestamp_ms)}</p>
          <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
            <span>{formatNumber(snap.total_records)} rows</span>
            <span>{snap.total_data_files} files</span>
            <span>{formatBytes(snap.total_size_bytes)}</span>
            {snap.has_deletes && (
              <span className="text-orange-600">
                {formatNumber(snap.total_delete_files)} deletes
              </span>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}
