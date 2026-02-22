"use client";

import { useState } from "react";
import { Search } from "lucide-react";

interface PathInputProps {
  onAnalyze: (path: string, catalog?: string, region?: string) => void;
  loading?: boolean;
}

export function PathInput({ onAnalyze, loading }: PathInputProps) {
  const [path, setPath] = useState("");
  const [catalog, setCatalog] = useState("");
  const [region, setRegion] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (path.trim()) {
      onAnalyze(path.trim(), catalog.trim() || undefined, region.trim() || undefined);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="flex gap-2">
        <input
          type="text"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="Path to Parquet file or directory (local or s3://...)"
          className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <button
          type="submit"
          disabled={!path.trim() || loading}
          className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Search className="h-4 w-4" />
          {loading ? "Loading..." : "Analyze"}
        </button>
      </div>

      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="text-xs text-muted-foreground hover:text-foreground"
      >
        {showAdvanced ? "Hide" : "Show"} advanced options
      </button>

      {showAdvanced && (
        <div className="grid grid-cols-2 gap-2">
          <input
            type="text"
            value={catalog}
            onChange={(e) => setCatalog(e.target.value)}
            placeholder="Catalog name (optional)"
            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
          />
          <input
            type="text"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            placeholder="AWS region (optional)"
            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
          />
        </div>
      )}
    </form>
  );
}
