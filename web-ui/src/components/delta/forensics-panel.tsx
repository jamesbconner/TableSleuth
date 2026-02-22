"use client";

import { formatBytes, formatNumber } from "@/lib/utils";
import type { DeltaForensicsResponse } from "@/lib/types";

interface ForensicsPanelProps {
  forensics: DeltaForensicsResponse;
}

const priorityColors = {
  high: "bg-red-100 text-red-800 border-red-200",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  low: "bg-blue-100 text-blue-800 border-blue-200",
};

const healthColors = {
  healthy: "text-green-600",
  degraded: "text-yellow-600",
  critical: "text-red-600",
};

export function ForensicsPanel({ forensics }: ForensicsPanelProps) {
  const { file_size_analysis: fsa, storage_waste: sw, checkpoint_health: ch, recommendations } =
    forensics;

  return (
    <div className="p-4 space-y-6">
      {/* File size distribution */}
      <section>
        <h3 className="font-semibold mb-3">File Size Distribution</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          {Object.entries(fsa.histogram).map(([bucket, count]) => (
            <div key={bucket} className="rounded border p-3 text-center">
              <p className="text-2xl font-bold">{count}</p>
              <p className="text-xs text-muted-foreground">{bucket}</p>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div className="rounded border p-2">
            <p className="text-xs text-muted-foreground">Small Files (&lt;10MB)</p>
            <p className="font-medium">
              {fsa.small_file_count} ({fsa.small_file_percentage.toFixed(1)}%)
            </p>
          </div>
          <div className="rounded border p-2">
            <p className="text-xs text-muted-foreground">Optimization Opportunity</p>
            <p className="font-medium">~{fsa.optimization_opportunity} files reducible</p>
          </div>
          <div className="rounded border p-2">
            <p className="text-xs text-muted-foreground">Total Size</p>
            <p className="font-medium">{formatBytes(fsa.total_size_bytes)}</p>
          </div>
        </div>
      </section>

      {/* Storage waste */}
      <section>
        <h3 className="font-semibold mb-3">Storage Waste</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <div className="rounded border p-2">
            <p className="text-xs text-muted-foreground">Active Files</p>
            <p className="font-medium">
              {sw.active_files.count} ({formatBytes(sw.active_files.total_size_bytes)})
            </p>
          </div>
          <div className="rounded border p-2">
            <p className="text-xs text-muted-foreground">Tombstoned Files</p>
            <p className="font-medium">
              {sw.tombstone_files.count} ({formatBytes(sw.tombstone_files.total_size_bytes)})
            </p>
          </div>
          <div className="rounded border p-2">
            <p className="text-xs text-muted-foreground">Waste %</p>
            <p
              className={`font-medium ${sw.waste_percentage > 30 ? "text-red-600" : sw.waste_percentage > 15 ? "text-yellow-600" : "text-green-600"}`}
            >
              {sw.waste_percentage.toFixed(1)}%
            </p>
          </div>
          <div className="rounded border p-2">
            <p className="text-xs text-muted-foreground">Reclaimable</p>
            <p className="font-medium">{formatBytes(sw.reclaimable_bytes)}</p>
          </div>
        </div>
      </section>

      {/* Checkpoint health */}
      <section>
        <h3 className="font-semibold mb-3">Checkpoint Health</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
          <div className="rounded border p-2">
            <p className="text-xs text-muted-foreground">Status</p>
            <p className={`font-semibold ${healthColors[ch.health_status]}`}>
              {ch.health_status.toUpperCase()}
            </p>
          </div>
          <div className="rounded border p-2">
            <p className="text-xs text-muted-foreground">Last Checkpoint</p>
            <p className="font-medium">
              {ch.last_checkpoint_version != null ? `v${ch.last_checkpoint_version}` : "None"}
            </p>
          </div>
          <div className="rounded border p-2">
            <p className="text-xs text-muted-foreground">Log Tail</p>
            <p className="font-medium">{ch.log_tail_length} files</p>
          </div>
        </div>
        {ch.issues.length > 0 && (
          <ul className="mt-2 text-sm text-yellow-700 list-disc list-inside">
            {ch.issues.map((issue, i) => (
              <li key={i}>{issue}</li>
            ))}
          </ul>
        )}
      </section>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <section>
          <h3 className="font-semibold mb-3">Recommendations</h3>
          <div className="space-y-2">
            {recommendations.map((rec, i) => (
              <div
                key={i}
                className={`rounded border p-3 text-sm ${priorityColors[rec.priority]}`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold">{rec.type}</span>
                  <span className="text-xs uppercase font-medium opacity-70">{rec.priority}</span>
                </div>
                <p className="mb-1">{rec.reason}</p>
                <p className="text-xs opacity-80">{rec.estimated_impact}</p>
                <code className="mt-1 block text-xs bg-white/50 rounded px-2 py-1">
                  {rec.command}
                </code>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
