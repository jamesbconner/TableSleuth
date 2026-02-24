"use client";

import { useState } from "react";
import { PathInput } from "@/components/parquet/path-input";
import { FileList } from "@/components/parquet/file-list";
import { FileDetailTabs } from "@/components/parquet/file-detail-tabs";
import { parquet as api } from "@/lib/api";
import type { FileRef, ParquetFileInfo, SampleResponse } from "@/lib/types";

export default function ParquetPage() {
  const [files, setFiles] = useState<FileRef[]>([]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [fileInfo, setFileInfo] = useState<ParquetFileInfo | null>(null);
  const [sample, setSample] = useState<SampleResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingInfo, setLoadingInfo] = useState(false);
  const [loadingSample, setLoadingSample] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async (path: string, catalog?: string, region?: string) => {
    setLoading(true);
    setError(null);
    setFiles([]);
    setSelectedPath(null);
    setFileInfo(null);
    setSample(null);
    try {
      const result = await api.analyze(path, catalog, region);
      setFiles(result.files);
      if (result.files.length === 1) {
        await handleSelectFile(result.files[0].path, region);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleSelectFile = async (path: string, region?: string) => {
    setSelectedPath(path);
    setFileInfo(null);
    setSample(null);
    setLoadingInfo(true);
    try {
      const info = await api.fileInfo(path, region);
      setFileInfo(info);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoadingInfo(false);
    }
  };

  const handleLoadSample = async () => {
    if (!selectedPath) return;
    setLoadingSample(true);
    try {
      const s = await api.sample(selectedPath, 100);
      setSample(s);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoadingSample(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-57px)]">
      <div className="border-b p-4 bg-card">
        <h1 className="text-xl font-semibold mb-3">Parquet Inspector</h1>
        <PathInput onAnalyze={handleAnalyze} loading={loading} />
        {error && (
          <div className="mt-3 rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* File list sidebar */}
        {files.length > 0 && (
          <div className="w-72 border-r overflow-auto bg-card shrink-0">
            <div className="px-4 py-2 border-b text-xs text-muted-foreground font-medium">
              {files.length} file{files.length !== 1 ? "s" : ""} found
            </div>
            <FileList
              files={files}
              selectedPath={selectedPath}
              onSelect={(path) => handleSelectFile(path)}
            />
          </div>
        )}

        {/* Detail panel */}
        <div className="flex-1 overflow-hidden">
          {loadingInfo ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Loading file metadata...
            </div>
          ) : fileInfo ? (
            <FileDetailTabs
              info={fileInfo}
              sample={sample}
              onLoadSample={handleLoadSample}
              loadingSample={loadingSample}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              {files.length > 0
                ? "Select a file to inspect"
                : "Enter a path above to discover Parquet files"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
