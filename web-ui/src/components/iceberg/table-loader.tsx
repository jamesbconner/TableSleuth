"use client";

import { useState } from "react";

interface TableLoaderProps {
  onLoad: (ref: { metadata_path?: string; catalog_name?: string; table_identifier?: string }) => void;
  loading?: boolean;
}

export function IcebergTableLoader({ onLoad, loading }: TableLoaderProps) {
  const [mode, setMode] = useState<"metadata" | "catalog">("metadata");
  const [metadataPath, setMetadataPath] = useState("");
  const [catalogName, setCatalogName] = useState("");
  const [tableIdentifier, setTableIdentifier] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === "metadata" && metadataPath.trim()) {
      onLoad({ metadata_path: metadataPath.trim() });
    } else if (mode === "catalog" && catalogName.trim() && tableIdentifier.trim()) {
      onLoad({ catalog_name: catalogName.trim(), table_identifier: tableIdentifier.trim() });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="flex gap-2">
        {(["metadata", "catalog"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
              mode === m
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:text-foreground"
            }`}
          >
            {m === "metadata" ? "Metadata File" : "Catalog"}
          </button>
        ))}
      </div>

      {mode === "metadata" ? (
        <div className="flex gap-2">
          <input
            type="text"
            value={metadataPath}
            onChange={(e) => setMetadataPath(e.target.value)}
            placeholder="Path to metadata.json (local or s3://...)"
            className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={!metadataPath.trim() || loading}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? "Loading..." : "Load"}
          </button>
        </div>
      ) : (
        <div className="flex gap-2">
          <input
            type="text"
            value={catalogName}
            onChange={(e) => setCatalogName(e.target.value)}
            placeholder="Catalog name"
            className="w-40 rounded-md border border-input bg-background px-3 py-2 text-sm"
          />
          <input
            type="text"
            value={tableIdentifier}
            onChange={(e) => setTableIdentifier(e.target.value)}
            placeholder="Table identifier (e.g. db.table)"
            className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={!catalogName.trim() || !tableIdentifier.trim() || loading}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? "Loading..." : "Load"}
          </button>
        </div>
      )}
    </form>
  );
}
