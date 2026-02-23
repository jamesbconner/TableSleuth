"use client";

import { useState } from "react";
import { gizmosql as api } from "@/lib/api";
import { formatBytes, formatNumber } from "@/lib/utils";
import type { PerformanceComparison } from "@/lib/types";

const PREDEFINED_QUERIES: { label: string; query: string }[] = [
  { label: "Full scan (COUNT)", query: "SELECT COUNT(*) FROM {table}" },
  { label: "Row stats", query: "SELECT COUNT(*) as row_count FROM {table}" },
  { label: "Sample rows (1000)", query: "SELECT * FROM {table} LIMIT 1000" },
];

interface ComparisonItem {
  id: string;
  label: string;
}

interface ComparisonPanelProps {
  format: "iceberg" | "delta";
  items: ComparisonItem[];
  // Iceberg table ref
  metadata_path?: string;
  catalog_name?: string;
  table_identifier?: string;
  // Delta table ref
  path?: string;
  storage_options?: Record<string, string>;
}

function DeltaPct({ value }: { value: number }) {
  const formatted = `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
  const cls =
    Math.abs(value) < 5
      ? "text-muted-foreground"
      : value > 0
      ? "text-red-600 dark:text-red-400"
      : "text-green-600 dark:text-green-400";
  return <span className={cls}>{formatted}</span>;
}

function MetricsGrid({
  labelA,
  labelB,
  metricsA,
  metricsB,
  timeDelta,
  filesDelta,
}: {
  labelA: string;
  labelB: string;
  metricsA: PerformanceComparison["metrics_a"];
  metricsB: PerformanceComparison["metrics_b"];
  timeDelta: number;
  filesDelta: number;
}) {
  const rows: { label: string; a: string; b: string; delta?: number }[] = [
    {
      label: "Execution time",
      a: `${metricsA.execution_time_ms.toFixed(1)} ms`,
      b: `${metricsB.execution_time_ms.toFixed(1)} ms`,
      delta: timeDelta,
    },
    {
      label: "Files scanned",
      a: String(metricsA.files_scanned),
      b: String(metricsB.files_scanned),
      delta: filesDelta,
    },
    {
      label: "Bytes scanned",
      a: formatBytes(metricsA.bytes_scanned),
      b: formatBytes(metricsB.bytes_scanned),
    },
    {
      label: "Rows scanned",
      a: formatNumber(metricsA.rows_scanned),
      b: formatNumber(metricsB.rows_scanned),
    },
    {
      label: "Rows returned",
      a: formatNumber(metricsA.rows_returned),
      b: formatNumber(metricsB.rows_returned),
    },
    {
      label: "Scan efficiency",
      a: `${metricsA.scan_efficiency.toFixed(1)}%`,
      b: `${metricsB.scan_efficiency.toFixed(1)}%`,
    },
    {
      label: "Peak memory",
      a: `${metricsA.memory_peak_mb.toFixed(1)} MB`,
      b: `${metricsB.memory_peak_mb.toFixed(1)} MB`,
    },
  ];

  return (
    <table className="w-full text-sm border-collapse">
      <thead>
        <tr className="border-b bg-muted/50">
          <th className="px-3 py-2 text-left text-xs text-muted-foreground">Metric</th>
          <th className="px-3 py-2 text-right text-xs font-mono">{labelA}</th>
          <th className="px-3 py-2 text-right text-xs font-mono">{labelB}</th>
          <th className="px-3 py-2 text-right text-xs text-muted-foreground">Δ</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.label} className="border-b hover:bg-muted/30">
            <td className="px-3 py-1.5 text-muted-foreground">{row.label}</td>
            <td className="px-3 py-1.5 text-right font-mono">{row.a}</td>
            <td className="px-3 py-1.5 text-right font-mono">{row.b}</td>
            <td className="px-3 py-1.5 text-right">
              {row.delta !== undefined ? <DeltaPct value={row.delta} /> : "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function ComparisonPanel({
  format,
  items,
  metadata_path,
  catalog_name,
  table_identifier,
  path,
  storage_options,
}: ComparisonPanelProps) {
  const [idA, setIdA] = useState(items[0]?.id ?? "");
  const [idB, setIdB] = useState(items[1]?.id ?? items[0]?.id ?? "");
  const [queryIdx, setQueryIdx] = useState(0);
  const [customQuery, setCustomQuery] = useState("");
  const [useCustom, setUseCustom] = useState(false);
  const [result, setResult] = useState<PerformanceComparison | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeQuery = useCustom ? customQuery : PREDEFINED_QUERIES[queryIdx].query;

  const handleRun = async () => {
    if (!idA || !idB) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.compare({
        format,
        metadata_path,
        catalog_name,
        table_identifier,
        path,
        storage_options,
        id_a: idA,
        id_b: idB,
        query: activeQuery,
      });
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const labelA = items.find((i) => i.id === idA)?.label ?? idA;
  const labelB = items.find((i) => i.id === idB)?.label ?? idB;

  if (items.length < 2) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground text-sm p-4">
        Load a table with at least 2 {format === "iceberg" ? "snapshots" : "versions"} to compare.
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Selector row */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-muted-foreground block mb-1">
            {format === "iceberg" ? "Snapshot A" : "Version A"}
          </label>
          <select
            value={idA}
            onChange={(e) => setIdA(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          >
            {items.map((i) => (
              <option key={i.id} value={i.id}>{i.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-muted-foreground block mb-1">
            {format === "iceberg" ? "Snapshot B" : "Version B"}
          </label>
          <select
            value={idB}
            onChange={(e) => setIdB(e.target.value)}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          >
            {items.map((i) => (
              <option key={i.id} value={i.id}>{i.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Query template */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <label className="text-xs text-muted-foreground">Query template</label>
          <button
            type="button"
            onClick={() => setUseCustom(!useCustom)}
            className="text-xs text-primary hover:underline"
          >
            {useCustom ? "Use preset" : "Custom query"}
          </button>
        </div>
        {useCustom ? (
          <textarea
            value={customQuery}
            onChange={(e) => setCustomQuery(e.target.value)}
            placeholder="SELECT COUNT(*) FROM {table}"
            rows={3}
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
          />
        ) : (
          <div className="flex gap-2 flex-wrap">
            {PREDEFINED_QUERIES.map((q, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setQueryIdx(i)}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                  queryIdx === i
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:text-foreground"
                }`}
              >
                {q.label}
              </button>
            ))}
          </div>
        )}
        <p className="text-xs text-muted-foreground font-mono">{activeQuery}</p>
      </div>

      {/* Run button */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleRun}
          disabled={loading || idA === idB || !activeQuery.trim()}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {loading ? "Running comparison…" : "Run Comparison"}
        </button>
        {idA === idB && (
          <span className="text-xs text-muted-foreground">Select two different {format === "iceberg" ? "snapshots" : "versions"}</span>
        )}
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          <MetricsGrid
            labelA={labelA}
            labelB={labelB}
            metricsA={result.metrics_a}
            metricsB={result.metrics_b}
            timeDelta={result.execution_time_delta_pct}
            filesDelta={result.files_scanned_delta_pct}
          />
          <div>
            <h4 className="font-medium mb-2 text-sm">Analysis</h4>
            <div className="rounded border bg-muted/30 p-3 text-sm space-y-1 whitespace-pre-wrap">
              {result.analysis}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
