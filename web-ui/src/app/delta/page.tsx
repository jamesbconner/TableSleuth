"use client";

import { useState } from "react";
import { DeltaTableLoader } from "@/components/delta/table-loader";
import { VersionHistory } from "@/components/delta/version-history";
import { ForensicsPanel } from "@/components/delta/forensics-panel";
import { delta as api } from "@/lib/api";
import type { DeltaForensicsResponse, DeltaLoadResponse, SnapshotInfo } from "@/lib/types";

type View = "history" | "forensics";

export default function DeltaPage() {
  const [tablePath, setTablePath] = useState<string | null>(null);
  const [currentSnapshot, setCurrentSnapshot] = useState<DeltaLoadResponse | null>(null);
  const [versions, setVersions] = useState<SnapshotInfo[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [forensics, setForensics] = useState<DeltaForensicsResponse | null>(null);
  const [view, setView] = useState<View>("history");
  const [loading, setLoading] = useState(false);
  const [loadingForensics, setLoadingForensics] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleLoad = async (path: string, version?: number) => {
    setLoading(true);
    setError(null);
    setVersions([]);
    setForensics(null);
    try {
      const [snap, vers] = await Promise.all([
        api.load({ path, version }),
        api.versions({ path }),
      ]);
      setTablePath(path);
      setCurrentSnapshot(snap);
      setVersions(vers.versions);
      setSelectedId(snap.snapshot_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleLoadForensics = async () => {
    if (!tablePath) return;
    setLoadingForensics(true);
    setView("forensics");
    try {
      const f = await api.forensics({ path: tablePath });
      setForensics(f);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoadingForensics(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-57px)]">
      <div className="border-b p-4 bg-card">
        <h1 className="text-xl font-semibold mb-3">Delta Lake Analyzer</h1>
        <DeltaTableLoader onLoad={handleLoad} loading={loading} />
        {error && (
          <div className="mt-3 rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
        {currentSnapshot && (
          <div className="mt-2 flex items-center gap-4">
            <span className="text-xs text-muted-foreground">
              v{currentSnapshot.current_version} · {versions.length} versions
            </span>
            <button
              onClick={handleLoadForensics}
              disabled={loadingForensics}
              className="text-xs text-primary hover:underline disabled:opacity-50"
            >
              {loadingForensics ? "Running forensics..." : "Run Forensics Analysis"}
            </button>
          </div>
        )}
      </div>

      {versions.length > 0 && (
        <div className="border-b px-4 flex gap-1 bg-card">
          {(["history", "forensics"] as View[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                view === v
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {v === "history" ? "Version History" : "Forensics"}
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {view === "history" && (
          <>
            {versions.length > 0 && (
              <div className="w-72 border-r overflow-auto bg-card shrink-0">
                <div className="px-4 py-2 border-b text-xs text-muted-foreground font-medium">
                  {versions.length} versions
                </div>
                <VersionHistory
                  versions={versions}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                />
              </div>
            )}
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              {versions.length > 0 ? "Select a version to inspect" : "Enter a Delta table path above"}
            </div>
          </>
        )}

        {view === "forensics" && (
          <div className="flex-1 overflow-auto">
            {loadingForensics ? (
              <div className="flex items-center justify-center h-full text-muted-foreground">
                Running forensic analysis...
              </div>
            ) : forensics ? (
              <ForensicsPanel forensics={forensics} />
            ) : (
              <div className="flex items-center justify-center h-full text-muted-foreground">
                Click "Run Forensics Analysis" above
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
