"use client";

import { formatBytes } from "@/lib/utils";
import type { ColumnStats } from "@/lib/types";

interface ColumnStatsTableProps {
  columns: ColumnStats[];
}

function fmt(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return v.toLocaleString();
  return String(v);
}

export function ColumnStatsTable({ columns }: ColumnStatsTableProps) {
  return (
    <div className="overflow-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-3 py-2 text-left font-medium">Column</th>
            <th className="px-3 py-2 text-left font-medium">Physical Type</th>
            <th className="px-3 py-2 text-left font-medium">Logical Type</th>
            <th className="px-3 py-2 text-right font-medium">Nulls</th>
            <th className="px-3 py-2 text-right font-medium">Distinct</th>
            <th className="px-3 py-2 text-left font-medium">Min</th>
            <th className="px-3 py-2 text-left font-medium">Max</th>
            <th className="px-3 py-2 text-left font-medium">Compression</th>
            <th className="px-3 py-2 text-right font-medium">Compressed</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((col) => (
            <tr key={col.name} className="border-b hover:bg-muted/30">
              <td className="px-3 py-2 font-mono font-medium">{col.name}</td>
              <td className="px-3 py-2 text-muted-foreground">{col.physical_type}</td>
              <td className="px-3 py-2 text-muted-foreground">{col.logical_type ?? "—"}</td>
              <td className="px-3 py-2 text-right">{fmt(col.null_count)}</td>
              <td className="px-3 py-2 text-right">{fmt(col.distinct_count)}</td>
              <td className="px-3 py-2 font-mono text-xs">{fmt(col.min_value)}</td>
              <td className="px-3 py-2 font-mono text-xs">{fmt(col.max_value)}</td>
              <td className="px-3 py-2">{col.compression}</td>
              <td className="px-3 py-2 text-right">
                {col.total_compressed_size != null
                  ? formatBytes(col.total_compressed_size)
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
