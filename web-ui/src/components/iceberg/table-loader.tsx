"use client";

import { useEffect, useState } from "react";
import { iceberg as api } from "@/lib/api";

interface TableLoaderProps {
  onLoad: (ref: { metadata_path?: string; catalog_name?: string; table_identifier?: string }) => void;
  loading?: boolean;
}

export function IcebergTableLoader({ onLoad, loading }: TableLoaderProps) {
  const [mode, setMode] = useState<"catalog" | "metadata">("catalog");

  // Catalog mode state
  const [catalogs, setCatalogs] = useState<string[]>([]);
  const [catalogName, setCatalogName] = useState("");
  const [tables, setTables] = useState<string[]>([]);
  const [tableIdentifier, setTableIdentifier] = useState("");
  const [loadingCatalogs, setLoadingCatalogs] = useState(false);
  const [loadingTables, setLoadingTables] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  // Metadata mode state
  const [metadataPath, setMetadataPath] = useState("");

  // Load catalog list on mount
  useEffect(() => {
    setLoadingCatalogs(true);
    api.catalogs()
      .then((res) => {
        setCatalogs(res.catalogs);
        if (res.catalogs.length > 0) setCatalogName(res.catalogs[0]);
      })
      .catch(() => setCatalogs([]))
      .finally(() => setLoadingCatalogs(false));
  }, []);

  const handleListTables = async () => {
    if (!catalogName) return;
    setLoadingTables(true);
    setCatalogError(null);
    setTables([]);
    setTableIdentifier("");
    try {
      const res = await api.catalogTables(catalogName);
      setTables(res.tables);
      if (res.tables.length > 0) setTableIdentifier(res.tables[0]);
    } catch (e) {
      setCatalogError(String(e));
    } finally {
      setLoadingTables(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === "catalog" && catalogName && tableIdentifier) {
      onLoad({ catalog_name: catalogName, table_identifier: tableIdentifier });
    } else if (mode === "metadata" && metadataPath.trim()) {
      onLoad({ metadata_path: metadataPath.trim() });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {/* Mode toggle */}
      <div className="flex gap-2">
        {(["catalog", "metadata"] as const).map((m) => (
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
            {m === "catalog" ? "Catalog" : "Metadata File"}
          </button>
        ))}
      </div>

      {mode === "catalog" ? (
        <div className="space-y-2">
          {/* Catalog selector */}
          <div className="flex gap-2 items-center">
            {loadingCatalogs ? (
              <span className="text-sm text-muted-foreground">Loading catalogs…</span>
            ) : catalogs.length > 0 ? (
              <select
                value={catalogName}
                onChange={(e) => {
                  setCatalogName(e.target.value);
                  setTables([]);
                  setTableIdentifier("");
                  setCatalogError(null);
                }}
                className="w-48 rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {catalogs.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={catalogName}
                onChange={(e) => setCatalogName(e.target.value)}
                placeholder="Catalog name (no .pyiceberg.yaml found)"
                className="w-56 rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            )}
            <button
              type="button"
              onClick={handleListTables}
              disabled={!catalogName || loadingTables}
              className="rounded-md border border-input bg-background px-3 py-2 text-sm hover:bg-muted disabled:opacity-50 transition-colors"
            >
              {loadingTables ? "Loading…" : "List Tables"}
            </button>
          </div>

          {catalogError && (
            <p className="text-xs text-destructive">{catalogError}</p>
          )}

          {/* Table selector */}
          <div className="flex gap-2">
            {tables.length > 0 ? (
              <select
                value={tableIdentifier}
                onChange={(e) => setTableIdentifier(e.target.value)}
                className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {tables.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                value={tableIdentifier}
                onChange={(e) => setTableIdentifier(e.target.value)}
                placeholder={
                  tables.length === 0 && !loadingTables
                    ? "Click 'List Tables' or type e.g. db.table"
                    : "Loading tables…"
                }
                className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            )}
            <button
              type="submit"
              disabled={!catalogName || !tableIdentifier || loading}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {loading ? "Loading…" : "Load"}
            </button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2">
          <input
            type="text"
            value={metadataPath}
            onChange={(e) => setMetadataPath(e.target.value)}
            placeholder="Path to metadata.json (local or s3://…)"
            className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={!metadataPath.trim() || loading}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? "Loading…" : "Load"}
          </button>
        </div>
      )}
    </form>
  );
}
