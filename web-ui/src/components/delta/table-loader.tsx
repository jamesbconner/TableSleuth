"use client";

import { useState } from "react";

interface DeltaTableLoaderProps {
  onLoad: (path: string, version?: number, storage_options?: Record<string, string>) => void;
  loading?: boolean;
}

export function DeltaTableLoader({ onLoad, loading }: DeltaTableLoaderProps) {
  const [path, setPath] = useState("");
  const [version, setVersion] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (path.trim()) {
      onLoad(path.trim(), version ? parseInt(version) : undefined);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={path}
        onChange={(e) => setPath(e.target.value)}
        placeholder="Path to Delta table (local or s3://...)"
        className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
      />
      <input
        type="number"
        value={version}
        onChange={(e) => setVersion(e.target.value)}
        placeholder="Version (optional)"
        className="w-32 rounded-md border border-input bg-background px-3 py-2 text-sm"
      />
      <button
        type="submit"
        disabled={!path.trim() || loading}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      >
        {loading ? "Loading..." : "Load"}
      </button>
    </form>
  );
}
