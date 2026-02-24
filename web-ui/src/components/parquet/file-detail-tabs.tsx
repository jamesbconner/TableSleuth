"use client";

import { useState } from "react";
import { formatBytes, formatNumber } from "@/lib/utils";
import { ColumnStatsTable } from "./column-stats-table";
import type { ParquetFileInfo, SampleResponse } from "@/lib/types";

type Tab = "schema" | "rowgroups" | "columns" | "sample";

interface FileDetailTabsProps {
  info: ParquetFileInfo;
  sample: SampleResponse | null;
  onLoadSample: () => void;
  loadingSample?: boolean;
}

export function FileDetailTabs({
  info,
  sample,
  onLoadSample,
  loadingSample,
}: FileDetailTabsProps) {
  const [tab, setTab] = useState<Tab>("schema");

  const tabs: { key: Tab; label: string }[] = [
    { key: "schema", label: "Schema" },
    { key: "rowgroups", label: `Row Groups (${info.num_row_groups})` },
    { key: "columns", label: `Column Stats (${info.num_columns})` },
    { key: "sample", label: "Data Sample" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* File overview */}
      <div className="px-4 py-3 border-b bg-muted/30 grid grid-cols-4 gap-3 text-sm">
        <div>
          <p className="text-xs text-muted-foreground">Size</p>
          <p className="font-medium">{formatBytes(info.file_size_bytes)}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Rows</p>
          <p className="font-medium">{formatNumber(info.num_rows)}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Row Groups</p>
          <p className="font-medium">{info.num_row_groups}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Columns</p>
          <p className="font-medium">{info.num_columns}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b px-4 flex gap-1">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto">
        {tab === "schema" && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-2 text-left font-medium">Column</th>
                <th className="px-4 py-2 text-left font-medium">Type</th>
                <th className="px-4 py-2 text-left font-medium">Nullable</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(info.schema).map(([name, meta]) => (
                <tr key={name} className="border-b hover:bg-muted/30">
                  <td className="px-4 py-2 font-mono">{name}</td>
                  <td className="px-4 py-2 text-muted-foreground">{meta.type}</td>
                  <td className="px-4 py-2">{meta.nullable ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === "rowgroups" && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-2 text-left font-medium">Group</th>
                <th className="px-4 py-2 text-right font-medium">Rows</th>
                <th className="px-4 py-2 text-right font-medium">Size</th>
                <th className="px-4 py-2 text-right font-medium">Columns</th>
              </tr>
            </thead>
            <tbody>
              {info.row_groups.map((rg) => (
                <tr key={rg.index} className="border-b hover:bg-muted/30">
                  <td className="px-4 py-2">Group {rg.index}</td>
                  <td className="px-4 py-2 text-right">{formatNumber(rg.num_rows)}</td>
                  <td className="px-4 py-2 text-right">{formatBytes(rg.total_byte_size)}</td>
                  <td className="px-4 py-2 text-right">{rg.columns.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === "columns" && <ColumnStatsTable columns={info.columns} />}

        {tab === "sample" && (
          <div className="p-4">
            {sample ? (
              <div className="overflow-auto">
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      {sample.columns.map((col) => (
                        <th key={col} className="px-3 py-2 text-left font-medium whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sample.rows.map((row, i) => (
                      <tr key={i} className="border-b hover:bg-muted/30">
                        {row.map((cell, j) => (
                          <td key={j} className="px-3 py-2 font-mono whitespace-nowrap">
                            {String(cell ?? "")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-2 text-xs text-muted-foreground">
                  Showing {sample.sampled_rows} of {formatNumber(sample.total_rows_in_file)} rows
                </p>
              </div>
            ) : (
              <button
                onClick={onLoadSample}
                disabled={loadingSample}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {loadingSample ? "Loading sample..." : "Load Data Sample"}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
