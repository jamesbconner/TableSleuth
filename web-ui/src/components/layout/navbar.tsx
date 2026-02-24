"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database, FileText, Grid3x3, House, ScanSearch, Settings, Triangle } from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Home", icon: House },
  { href: "/parquet", label: "Parquet", icon: FileText },
  { href: "/iceberg", label: "Iceberg", icon: Grid3x3 },
  { href: "/delta", label: "Delta", icon: Triangle },
  { href: "/gizmosql", label: "GizmoSQL", icon: Database },
  { href: "/settings", label: "Settings", icon: Settings },
];

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 240 240"
      fill="currentColor"
      aria-hidden="true"
      className={className}
    >
      <g transform="translate(0,240) scale(0.1,-0.1)">
        <path d="M970 2301 c-305 -68 -555 -237 -727 -493 -301 -451 -241 -1056 143
-1442 115 -116 290 -228 422 -271 49 -16 55 -16 77 -1 24 16 25 20 25 135 l0
118 -88 -5 c-103 -5 -183 13 -231 54 -17 14 -50 62 -73 106 -38 74 -66 108
-144 177 -26 23 -27 24 -9 37 43 32 130 1 185 -65 96 -117 133 -148 188 -160
49 -10 94 -6 162 14 9 3 21 24 27 48 6 23 22 58 35 77 l24 35 -81 16 c-170 35
-275 96 -344 200 -64 96 -85 179 -86 334 0 146 16 206 79 288 28 36 31 47 23
68 -15 36 -11 188 5 234 13 34 20 40 47 43 45 5 129 -24 214 -72 l73 -42 64
15 c91 21 364 20 446 0 l62 -16 58 35 c77 46 175 82 224 82 39 0 39 -1 55 -52
17 -59 20 -166 5 -217 -8 -30 -6 -39 16 -68 109 -144 121 -383 29 -579 -62
-129 -193 -219 -369 -252 l-84 -16 31 -55 32 -56 3 -223 4 -223 25 -16 c23
-15 28 -15 76 2 80 27 217 101 292 158 446 334 590 933 343 1431 -145 293
-419 518 -733 602 -137 36 -395 44 -525 15z" />
      </g>
    </svg>
  );
}

export function NavBar() {
  const pathname = usePathname();

  return (
    <nav className="border-b bg-card px-4 py-3 flex items-center gap-6">
      <Link href="/" className="font-semibold text-lg text-primary flex items-center gap-2">
        <ScanSearch className="h-5 w-5" />
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
      <div className="ml-auto">
        <a
          href="https://github.com/jamesbconner/TableSleuth"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="TableSleuth on GitHub"
          className="flex items-center p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
        >
          <GitHubIcon className="h-5 w-5" />
        </a>
      </div>
    </nav>
  );
}
