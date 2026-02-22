import Link from "next/link";
import { Database, FileText, GitBranch, Terminal } from "lucide-react";

const formats = [
  {
    href: "/parquet",
    label: "Parquet",
    icon: FileText,
    description:
      "Inspect Parquet files and directories. Explore schema, row groups, column stats, and data samples.",
    color: "text-blue-600",
    bg: "bg-blue-50 hover:bg-blue-100",
  },
  {
    href: "/iceberg",
    label: "Apache Iceberg",
    icon: Database,
    description:
      "Analyze Iceberg table snapshots, schema evolution, MOR overhead, and compare snapshot deltas.",
    color: "text-purple-600",
    bg: "bg-purple-50 hover:bg-purple-100",
  },
  {
    href: "/delta",
    label: "Delta Lake",
    icon: GitBranch,
    description:
      "Examine Delta table version history, storage waste, checkpoint health, and optimization recommendations.",
    color: "text-green-600",
    bg: "bg-green-50 hover:bg-green-100",
  },
  {
    href: "/gizmosql",
    label: "GizmoSQL",
    icon: Terminal,
    description:
      "Run SQL queries and column profiling against Parquet/Iceberg data via GizmoSQL DuckDB Flight SQL.",
    color: "text-orange-600",
    bg: "bg-orange-50 hover:bg-orange-100",
  },
];

export default function HomePage() {
  return (
    <div className="container mx-auto px-4 py-12 max-w-4xl">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold mb-3">TableSleuth</h1>
        <p className="text-muted-foreground text-lg">
          Forensic analysis for open table formats — Parquet, Apache Iceberg, Delta Lake.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {formats.map(({ href, label, icon: Icon, description, color, bg }) => (
          <Link
            key={href}
            href={href}
            className={`rounded-xl border p-6 transition-colors ${bg} flex flex-col gap-3`}
          >
            <div className="flex items-center gap-3">
              <Icon className={`h-6 w-6 ${color}`} />
              <span className="font-semibold text-lg">{label}</span>
            </div>
            <p className="text-sm text-muted-foreground">{description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
