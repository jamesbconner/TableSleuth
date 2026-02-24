"use client";

import { useState } from "react";
import { DeltaTableLoader } from "@/components/delta/table-loader";
import { VersionHistory } from "@/components/delta/version-history";
import { VersionDetail } from "@/components/delta/version-detail";
import { ForensicsPanel } from "@/components/delta/forensics-panel";
import { DataSample } from "@/components/shared/data-sample";
import { ComparisonPanel } from "@/components/shared/comparison-panel";
import { delta as api } from "@/lib/api";
import type { DeltaForensicsResponse, DeltaLoadResponse, DeltaSchemaField, SnapshotInfo } from "@/lib/types";

type RightTab = "details" | "forensics" | "sample" | "compare";

export default function DeltaPage() {
  const [tablePath, setTablePath] = useState<string | null>(null);
  const [currentSnapshot, setCurrentSnapshot] = useState<DeltaLoadResponse | null>(null);
  const [versions, setVersions] = useState<SnapshotInfo[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [schema, setSchema] = useState<DeltaSchemaField[] | null>(null);
  const [loadingSchema, setLoadingSchema] = useState(false);
  const [forensics, setForensics] = useState<DeltaForensicsResponse | null>(null);
  const [loadingForensics, setLoadingForensics] = useState(false);
  const [rightTab, setRightTab] = useState<RightTab>("details");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedVersion = versions.find((v) => v.snapshot_id === selectedId) ?? null;

  const loadSchema = async (path: string, version: number) => {
    setLoadingSchema(true);
    setSchema(null);
    try {
      const res = await api.schema({ path, version });
      setSchema(res.fields);
    } catch {
      setSchema(null);
    } finally {
      setLoadingSchema(false);
    }
  };

  const handleLoad = async (path: string, version?: number) => {
    setLoading(true);
    setError(null);
    setVersions([]);
    setForensics(null);
    setSchema(null);
    setRightTab("details");
    try {
      const [snap, vers] = await Promise.all([
        api.load({ path, version }),
        api.versions({ path }),
      ]);
      setTablePath(path);
      setCurrentSnapshot(snap);
      setVersions(vers.versions);
      setSelectedId(snap.snapshot_id);
      loadSchema(path, snap.snapshot_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (id: number) => {
    setSelectedId(id);
    setRightTab("details");
    if (tablePath) {
      loadSchema(tablePath, id);
    }
  };

  const handleLoadForensics = async () => {
    if (!tablePath) return;
    setLoadingForensics(true);
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
          <div className="mt-2 text-xs text-muted-foreground">
            v{currentSnapshot.current_version} · {versions.length} versions
          </div>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {versions.length > 0 && (
          <div className="w-72 border-r overflow-auto bg-card shrink-0">
            <div className="px-4 py-2 border-b text-xs text-muted-foreground font-medium">
              {versions.length} versions
            </div>
            <VersionHistory
              versions={versions}
              selectedId={selectedId}
              onSelect={handleSelect}
            />
          </div>
        )}

        <div className="flex-1 overflow-hidden flex flex-col">
          {selectedVersion ? (
            <>
              <div className="border-b px-4 flex gap-1 bg-card shrink-0">
                {(["details", "forensics", "sample", "compare"] as RightTab[]).map((t) => (
                  <button
                    key={t}
                    onClick={() => setRightTab(t)}
                    className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                      rightTab === t
                        ? "border-primary text-primary"
                        : "border-transparent text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {t === "details" ? "Details" : t === "forensics" ? "Forensics" : t === "sample" ? "Data Sample" : "Compare"}
                  </button>
                ))}
              </div>

              <div className="flex-1 overflow-auto">
                {rightTab === "details" && (
                  <VersionDetail
                    version={selectedVersion}
                    schema={schema}
                    loadingSchema={loadingSchema}
                  />
                )}
                {rightTab === "forensics" && (
                  <div className="p-4 space-y-4">
                    {!forensics && (
                      <button
                        onClick={handleLoadForensics}
                        disabled={loadingForensics}
                        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                      >
                        {loadingForensics ? "Running forensics…" : "Run Forensic Analysis"}
                      </button>
                    )}
                    {loadingForensics && (
                      <div className="text-sm text-muted-foreground">Running forensic analysis…</div>
                    )}
                    {forensics && <ForensicsPanel forensics={forensics} />}
                  </div>
                )}
                {rightTab === "sample" && (
                  <DataSample filePath={selectedVersion.data_files[0]?.path ?? null} />
                )}
                {rightTab === "compare" && tablePath && (
                  <ComparisonPanel
                    format="delta"
                    items={[...versions].sort((a, b) => b.timestamp_ms - a.timestamp_ms).map((v) => ({
                      id: String(v.snapshot_id),
                      label: `v${v.snapshot_id} · ${v.operation} · ${new Date(v.timestamp_ms).toLocaleString()}`,
                    }))}
                    path={tablePath}
                  />
                )}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              {versions.length > 0 ? "Select a version to inspect" : "Enter a Delta table path above"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
