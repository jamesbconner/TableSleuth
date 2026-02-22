"use client";

import { useEffect, useState } from "react";
import { SqlEditor } from "@/components/gizmosql/sql-editor";
import { ResultsGrid } from "@/components/gizmosql/results-grid";
import { gizmosql as api } from "@/lib/api";
import type { GizmoStatus, QueryResult } from "@/lib/types";

export default function GizmoSQLPage() {
  const [status, setStatus] = useState<GizmoStatus | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.status().then(setStatus).catch(() => setStatus({ connected: false, error: "Could not reach server" }));
  }, []);

  const handleExecute = async (sql: string) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.query(sql);
      setResult(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-6 max-w-5xl">
      <h1 className="text-xl font-semibold mb-4">GizmoSQL Query Console</h1>

      {/* Connection status */}
      {status && (
        <div
          className={`mb-4 text-sm px-3 py-2 rounded border ${
            status.connected
              ? "bg-green-50 border-green-200 text-green-800"
              : "bg-red-50 border-red-200 text-red-800"
          }`}
        >
          {status.connected ? (
            <>Connected · {status.version}</>
          ) : (
            <>Not connected · {status.error}</>
          )}
        </div>
      )}

      <SqlEditor onExecute={handleExecute} loading={loading} />

      {error && (
        <div className="mt-4 rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-4">
          <ResultsGrid result={result} />
        </div>
      )}
    </div>
  );
}
