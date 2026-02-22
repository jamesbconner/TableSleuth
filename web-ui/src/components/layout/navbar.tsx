"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database, FileText, GitBranch, Settings, Terminal, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Home", icon: Zap },
  { href: "/parquet", label: "Parquet", icon: FileText },
  { href: "/iceberg", label: "Iceberg", icon: Database },
  { href: "/delta", label: "Delta", icon: GitBranch },
  { href: "/gizmosql", label: "GizmoSQL", icon: Terminal },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <nav className="border-b bg-card px-4 py-3 flex items-center gap-6">
      <Link href="/" className="font-semibold text-lg text-primary flex items-center gap-2">
        <Zap className="h-5 w-5" />
        TableSleuth
      </Link>
      <div className="flex items-center gap-1">
        {navItems.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
              pathname === href
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
