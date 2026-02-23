"use client";

import { formatBytes, formatNumber, formatTimestamp } from "@/lib/utils";
import type { DeltaSchemaField, SnapshotInfo } from "@/lib/types";

interface VersionDetailProps {
  version: SnapshotInfo;
  schema?: DeltaSchemaField[] | null;
  loadingSchema?: boolean;
}

export function VersionDetail({ version, schema, loadingSchema }: VersionDetailProps) {
  const totalSize = version.data_files.reduce((s, f) => s + f.file_size_bytes, 0);
  const totalRecords = version.data_files.reduce(
    (s, f) => s + (f.record_count ?? 0),
    0
  );

  return (
    <div className="space-y-6 p-4">
      {/* Summary */}
      <div>
        <h3 className="font-semibold mb-3">Version {version.snapshot_id}</h3>
        <div className="grid grid-cols-3 gap-3 text-sm">
          {[
            ["Timestamp", formatTimestamp(version.timestamp_ms)],
            ["Operation", version.operation],
            ["Data Files", formatNumber(version.data_files.length)],
            ["Delete Files", formatNumber(version.delete_files.length)],
            ["Total Records", formatNumber(totalRecords)],
            ["Total Size", formatBytes(totalSize)],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded border p-2">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="font-medium">{value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Operation summary */}
      {Object.keys(version.summary).length > 0 && (
        <div>
          <h4 className="font-medium mb-2">Commit Summary</h4>
          <div className="rounded border bg-muted/30 p-3 text-xs space-y-1 font-mono">
            {Object.entries(version.summary).map(([k, v]) => (
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
        {loadingSchema ? (
          <p className="text-sm text-muted-foreground">Loading schema…</p>
        ) : schema && schema.length > 0 ? (
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-3 py-2 text-left">Field</th>
                <th className="px-3 py-2 text-left">Type</th>
                <th className="px-3 py-2 text-left">Nullable</th>
              </tr>
            </thead>
            <tbody>
              {schema.map((f) => (
                <tr key={f.name} className="border-b hover:bg-muted/30">
                  <td className="px-3 py-1.5 font-mono">{f.name}</td>
                  <td className="px-3 py-1.5 text-muted-foreground">{f.type}</td>
                  <td className="px-3 py-1.5">{f.nullable ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-muted-foreground">No schema available.</p>
        )}
      </div>

      {/* Data files */}
      <div>
        <h4 className="font-medium mb-2">
          Data Files ({version.data_files.length})
        </h4>
        {version.data_files.length === 0 ? (
          <p className="text-sm text-muted-foreground">No data files in this version.</p>
        ) : (
          <div className="max-h-64 overflow-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2 text-left">Path</th>
                  <th className="px-3 py-2 text-right">Size</th>
                  <th className="px-3 py-2 text-right">Records</th>
                </tr>
              </thead>
              <tbody>
                {version.data_files.map((f, i) => (
                  <tr key={i} className="border-b hover:bg-muted/30">
                    <td className="px-3 py-1.5 font-mono truncate max-w-xs">{f.path}</td>
                    <td className="px-3 py-1.5 text-right">{formatBytes(f.file_size_bytes)}</td>
                    <td className="px-3 py-1.5 text-right">
                      {f.record_count != null ? formatNumber(f.record_count) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete files */}
      {version.delete_files.length > 0 && (
        <div>
          <h4 className="font-medium mb-2 text-orange-600">
            Delete Files ({version.delete_files.length})
          </h4>
          <div className="max-h-40 overflow-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2 text-left">Path</th>
                  <th className="px-3 py-2 text-right">Size</th>
                </tr>
              </thead>
              <tbody>
                {version.delete_files.map((f, i) => (
                  <tr key={i} className="border-b hover:bg-muted/30">
                    <td className="px-3 py-1.5 font-mono truncate max-w-xs">{f.path}</td>
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
