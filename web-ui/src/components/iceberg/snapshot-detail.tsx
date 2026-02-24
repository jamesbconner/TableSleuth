"use client";

import { formatBytes, formatNumber, formatTimestamp } from "@/lib/utils";
import type { IcebergSnapshotDetails } from "@/lib/types";

interface SnapshotDetailProps {
  details: IcebergSnapshotDetails;
}

export function SnapshotDetail({ details }: SnapshotDetailProps) {
  const { snapshot_info: snap, data_files, delete_files, schema, partition_spec } = details;

  return (
    <div className="space-y-6 p-4">
      {/* Summary */}
      <div>
        <h3 className="font-semibold mb-3">Snapshot {snap.snapshot_id}</h3>
        <div className="grid grid-cols-3 gap-3 text-sm">
          {[
            ["Timestamp", formatTimestamp(snap.timestamp_ms)],
            ["Operation", snap.operation],
            ["Total Records", formatNumber(snap.total_records)],
            ["Data Files", snap.total_data_files],
            ["Delete Files", snap.total_delete_files],
            ["Total Size", formatBytes(snap.total_size_bytes)],
            ["Delete Ratio", (snap.delete_ratio * 100).toFixed(2) + "%"],
            ["Read Amplification", snap.read_amplification.toFixed(2) + "x"],
            ["Schema ID", snap.schema_id],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded border p-2">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="font-medium">{value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Commit Summary */}
      {Object.keys(snap.summary).length > 0 && (
        <div>
          <h4 className="font-medium mb-2">Commit Summary</h4>
          <div className="rounded border bg-muted/30 p-3 text-xs space-y-1 font-mono">
            {Object.entries(snap.summary).map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <span className="text-muted-foreground shrink-0">{k}:</span>
                <span className="break-all">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Schema */}
      <div>
        <h4 className="font-medium mb-2">Schema</h4>
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-3 py-2 text-left">Field</th>
              <th className="px-3 py-2 text-left">Type</th>
              <th className="px-3 py-2 text-left">Required</th>
            </tr>
          </thead>
          <tbody>
            {schema.fields.map((f) => (
              <tr key={f.field_id} className="border-b hover:bg-muted/30">
                <td className="px-3 py-1.5 font-mono">{f.name}</td>
                <td className="px-3 py-1.5 text-muted-foreground">{f.field_type}</td>
                <td className="px-3 py-1.5">{f.required ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Partition spec */}
      <div>
        <h4 className="font-medium mb-2">Partition Spec</h4>
        {partition_spec.fields.length === 0 ? (
          <p className="text-sm text-muted-foreground">Unpartitioned</p>
        ) : (
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-3 py-2 text-left">Field</th>
                <th className="px-3 py-2 text-left">Transform</th>
              </tr>
            </thead>
            <tbody>
              {partition_spec.fields.map((f) => (
                <tr key={f.field_id} className="border-b hover:bg-muted/30">
                  <td className="px-3 py-1.5 font-mono">{f.name}</td>
                  <td className="px-3 py-1.5 text-muted-foreground">{f.transform}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Data files */}
      <div>
        <h4 className="font-medium mb-2">Data Files ({data_files.length})</h4>
        <div className="max-h-48 overflow-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-3 py-2 text-left">Path</th>
                <th className="px-3 py-2 text-right">Size</th>
                <th className="px-3 py-2 text-right">Records</th>
              </tr>
            </thead>
            <tbody>
              {data_files.map((f, i) => (
                <tr key={i} className="border-b hover:bg-muted/30">
                  <td className="px-3 py-1.5 font-mono truncate max-w-xs">{f.file_path}</td>
                  <td className="px-3 py-1.5 text-right">{formatBytes(f.file_size_bytes)}</td>
                  <td className="px-3 py-1.5 text-right">
                    {f.record_count != null ? formatNumber(f.record_count) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Delete files */}
      {delete_files.length > 0 && (
        <div>
          <h4 className="font-medium mb-2 text-orange-600">
            Delete Files ({delete_files.length})
          </h4>
          <div className="max-h-36 overflow-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2 text-left">Path</th>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-right">Size</th>
                </tr>
              </thead>
              <tbody>
                {delete_files.map((f, i) => (
                  <tr key={i} className="border-b hover:bg-muted/30">
                    <td className="px-3 py-1.5 font-mono truncate max-w-xs">{f.file_path}</td>
                    <td className="px-3 py-1.5">{f.content}</td>
                    <td className="px-3 py-1.5 text-right">{formatBytes(f.file_size_bytes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
