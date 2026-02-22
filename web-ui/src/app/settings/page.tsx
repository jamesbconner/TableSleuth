"use client";

import { useEffect, useState } from "react";
import { config as api } from "@/lib/api";
import type { AppConfig, ConfigStatus } from "@/lib/types";

export default function SettingsPage() {
  const [cfg, setCfg] = useState<AppConfig | null>(null);
  const [status, setStatus] = useState<ConfigStatus | null>(null);
  const [pyiceberg, setPyiceberg] = useState<Record<string, unknown> | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.get(), api.status(), api.getPyiceberg()])
      .then(([c, s, p]) => {
        setCfg(c);
        setStatus(s);
        setPyiceberg(p.config);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const handleSave = async () => {
    if (!cfg) return;
    setSaving(true);
    setError(null);
    try {
      await api.save(cfg);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  if (!cfg) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Loading settings...
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-6 max-w-2xl">
      <h1 className="text-xl font-semibold mb-6">Settings</h1>

      {status && (
        <div className="mb-4 rounded border p-3 text-sm bg-muted/30">
          <p className="font-medium mb-1">Active Configuration</p>
          <p className="text-muted-foreground">
            File: {status.config_file ?? "defaults (no file found)"}
          </p>
          {Object.entries(status.env_overrides)
            .filter(([, v]) => v)
            .map(([k]) => (
              <p key={k} className="text-xs text-blue-600">
                ENV override: {k}
              </p>
            ))}
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Catalog settings */}
      <section className="mb-6">
        <h2 className="font-medium mb-3">Catalog</h2>
        <label className="block text-sm mb-1 text-muted-foreground">Default catalog</label>
        <input
          type="text"
          value={cfg.catalog.default ?? ""}
          onChange={(e) => setCfg({ ...cfg, catalog: { default: e.target.value || null } })}
          placeholder="e.g. glue, local_sqlite"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        />
      </section>

      {/* GizmoSQL settings */}
      <section className="mb-6">
        <h2 className="font-medium mb-3">GizmoSQL</h2>
        <div className="space-y-3">
          {[
            { label: "URI", key: "uri", placeholder: "grpc+tls://localhost:31337" },
            { label: "Username", key: "username", placeholder: "gizmosql_username" },
            { label: "Password", key: "password", placeholder: "gizmosql_password", type: "password" },
          ].map(({ label, key, placeholder, type }) => (
            <div key={key}>
              <label className="block text-sm mb-1 text-muted-foreground">{label}</label>
              <input
                type={type ?? "text"}
                value={cfg.gizmosql[key as keyof typeof cfg.gizmosql] as string}
                onChange={(e) =>
                  setCfg({ ...cfg, gizmosql: { ...cfg.gizmosql, [key]: e.target.value } })
                }
                placeholder={placeholder}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
          ))}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="tls_skip_verify"
              checked={cfg.gizmosql.tls_skip_verify}
              onChange={(e) =>
                setCfg({
                  ...cfg,
                  gizmosql: { ...cfg.gizmosql, tls_skip_verify: e.target.checked },
                })
              }
            />
            <label htmlFor="tls_skip_verify" className="text-sm">
              Skip TLS verification
            </label>
          </div>
        </div>
      </section>

      {/* PyIceberg config (read-only preview) */}
      {pyiceberg && Object.keys(pyiceberg).length > 0 && (
        <section className="mb-6">
          <h2 className="font-medium mb-3">PyIceberg Config (.pyiceberg.yaml)</h2>
          <pre className="rounded border bg-muted/30 p-3 text-xs overflow-auto max-h-48">
            {JSON.stringify(pyiceberg, null, 2)}
          </pre>
        </section>
      )}

      <button
        onClick={handleSave}
        disabled={saving}
        className="rounded-md bg-primary px-6 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      >
        {saved ? "Saved!" : saving ? "Saving..." : "Save Configuration"}
      </button>
    </div>
  );
}
