"use client";

import { FileText } from "lucide-react";
import { formatBytes } from "@/lib/utils";
import type { FileRef } from "@/lib/types";

interface FileListProps {
  files: FileRef[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
}

export function FileList({ files, selectedPath, onSelect }: FileListProps) {
  if (files.length === 0) {
    return <p className="text-sm text-muted-foreground p-4">No files found.</p>;
  }

  return (
    <div className="divide-y">
      {files.map((file) => (
        <button
          key={file.path}
          onClick={() => onSelect(file.path)}
          className={`w-full text-left px-4 py-3 hover:bg-accent transition-colors flex items-start gap-3 ${
            selectedPath === file.path ? "bg-accent" : ""
          }`}
        >
          <FileText className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
          <div className="min-w-0">
            <p className="text-sm font-medium truncate">{file.path.split("/").pop()}</p>
            <p className="text-xs text-muted-foreground truncate">{file.path}</p>
            <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
              <span>{formatBytes(file.file_size_bytes)}</span>
              {file.record_count != null && (
                <span>{file.record_count.toLocaleString()} rows</span>
              )}
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}
