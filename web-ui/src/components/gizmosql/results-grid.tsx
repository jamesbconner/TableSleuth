"use client";

import { formatDuration, formatNumber } from "@/lib/utils";
import type { QueryResult } from "@/lib/types";

interface ResultsGridProps {
  result: QueryResult;
}

export function ResultsGrid({ result }: ResultsGridProps) {
  return (
    <div>
      <div className="flex items-center gap-3 text-xs text-muted-foreground mb-2">
        <span>{formatNumber(result.row_count)} rows</span>
        <span>·</span>
        <span>{formatDuration(result.elapsed_ms)}</span>
      </div>
      <div className="overflow-auto max-h-[60vh] rounded border">
        <table className="w-full text-sm border-collapse">
          <thead className="sticky top-0">
            <tr className="bg-muted/80 border-b">
              {result.columns.map((col) => (
                <th key={col} className="px-3 py-2 text-left font-medium whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.map((row, i) => (
              <tr key={i} className="border-b hover:bg-muted/30">
                {row.map((cell, j) => (
                  <td key={j} className="px-3 py-1.5 font-mono whitespace-nowrap">
                    {cell == null ? (
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
    </div>
  );
}
