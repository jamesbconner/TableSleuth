"use client";

import { formatBytes, formatNumber, formatTimestamp } from "@/lib/utils";
import type { SnapshotInfo } from "@/lib/types";

interface VersionHistoryProps {
  versions: SnapshotInfo[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export function VersionHistory({ versions, selectedId, onSelect }: VersionHistoryProps) {
  return (
    <div className="divide-y">
      {[...versions].reverse().map((v) => (
        <button
          key={v.snapshot_id}
          onClick={() => onSelect(v.snapshot_id)}
          className={`w-full text-left px-4 py-3 hover:bg-accent transition-colors ${
            selectedId === v.snapshot_id ? "bg-accent" : ""
          }`}
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded">
              {v.operation}
            </span>
            <span className="text-xs font-mono text-muted-foreground">v{v.snapshot_id}</span>
          </div>
          <p className="text-xs text-muted-foreground">{formatTimestamp(v.timestamp_ms)}</p>
          <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
            <span>{formatNumber(v.data_files.length)} files</span>
            <span>{formatBytes(v.data_files.reduce((s, f) => s + f.file_size_bytes, 0))}</span>
            <span>{formatNumber(v.data_files.reduce((s, f) => s + (f.record_count ?? 0), 0))} rows</span>
          </div>
        </button>
      ))}
    </div>
  );
}
