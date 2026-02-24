"use client";

import { useState } from "react";
import { Play } from "lucide-react";

interface SqlEditorProps {
  onExecute: (sql: string) => void;
  loading?: boolean;
}

export function SqlEditor({ onExecute, loading }: SqlEditorProps) {
  const [sql, setSql] = useState("SELECT 1 AS test");

  const handleExecute = () => {
    if (sql.trim()) onExecute(sql.trim());
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      handleExecute();
    }
  };

  return (
    <div className="space-y-2">
      <textarea
        value={sql}
        onChange={(e) => setSql(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={6}
        placeholder="Enter SQL query... (Ctrl+Enter to run)"
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono resize-y focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      <button
        onClick={handleExecute}
        disabled={!sql.trim() || loading}
        className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      >
        <Play className="h-4 w-4" />
        {loading ? "Running..." : "Run Query (Ctrl+Enter)"}
      </button>
    </div>
  );
}
