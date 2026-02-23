"use client";

import { useState } from "react";
import { parquet as api } from "@/lib/api";
import type { SampleResponse } from "@/lib/types";

interface DataSampleProps {
  filePath: string | null;
}

export function DataSample({ filePath }: DataSampleProps) {
  const [data, setData] = useState<SampleResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = async () => {
    if (!filePath) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.sample(filePath, 50);
      setData(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  if (!filePath) {
    return (
      <div className="flex items-center justify-center h-32 text-muted-foreground text-sm p-4">
        No data files in this snapshot.
      </div>
    );
  }

  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center gap-3">
        <button
          onClick={handleLoad}
          disabled={loading || !!data}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {loading ? "Loading sample…" : data ? "Sample loaded" : "Load Data Sample (50 rows)"}
        </button>
        {data && (
          <span className="text-xs text-muted-foreground">
            Showing {data.sampled_rows} of {data.total_rows_in_file} rows · {data.columns.length} columns
          </span>
        )}
      </div>

      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      {data && (
        <div className="overflow-auto max-h-[calc(100vh-280px)] border rounded">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="border-b bg-muted/50 sticky top-0">
                {data.columns.map((col) => (
                  <th key={col} className="px-3 py-2 text-left font-medium whitespace-nowrap border-r last:border-r-0">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row, i) => (
                <tr key={i} className="border-b hover:bg-muted/30">
                  {(row as unknown[]).map((cell, j) => (
                    <td key={j} className="px-3 py-1.5 whitespace-nowrap border-r last:border-r-0">
                      {cell === null || cell === undefined ? (
                        <span className="text-muted-foreground italic">null</span>
                      ) : (
                        String(cell)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
