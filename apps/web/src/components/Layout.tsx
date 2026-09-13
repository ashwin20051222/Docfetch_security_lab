import { NavLink, Outlet } from "react-router-dom";

import { useAppMeta } from "../hooks";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/retrieve", label: "Retrieve" },
  { to: "/lab", label: "Security Lab" },
  { to: "/targets", label: "Targets" },
  { to: "/findings", label: "Findings" },
  { to: "/settings", label: "Settings" },
];

export function Layout() {
  const meta = useAppMeta();

  return (
    <div className="min-h-screen">
      <header
        className="fixed top-0 left-0 right-0 z-50 border-b"
        style={{
          background: "var(--surface-container-lowest)",
          borderColor: "var(--surface-container)",
        }}
      >
        <div className="h-16 mx-auto px-6 flex items-center justify-between gap-3" style={{ maxWidth: "80rem" }}>
          <div className="flex items-center gap-2">
            <span
              aria-hidden
              className="inline-flex items-center justify-center w-9 h-9 rounded-xl"
              style={{ background: "color-mix(in srgb, var(--primary-container) 18%, white)" }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path
                  d="M8 3h8a2 2 0 0 1 2 2v16l-3-1.5L12 21l-3-1.5L6 21V5a2 2 0 0 1 2-2Z"
                  stroke="var(--primary)"
                  strokeWidth="1.6"
                />
                <path d="M9 8h6M9 12h6" stroke="var(--primary)" strokeWidth="1.6" strokeLinecap="round" />
              </svg>
            </span>
            <span className="app-headline-sm" style={{ fontWeight: 600 }}>
              DocFetch
            </span>
            <span className="app-label-sm text-secondary" style={{ textTransform: "none", letterSpacing: "0.02em" }}>
              Security Lab
            </span>
          </div>

          <nav className="hidden md:flex items-center gap-1 p-1 rounded-xl" style={{ background: "var(--surface-container-low)" }}>
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) => `app-navtab ${isActive ? "active" : ""}`}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <span
              className="app-chip"
              style={
                meta.health?.status === "ok"
                  ? { background: "#ecfdf5", borderColor: "#a7f3d0", color: "#047857" }
                  : { background: "var(--error-container)", borderColor: "#fecaca", color: "var(--on-error-container)" }
              }
            >
              {meta.loading ? "…" : meta.error ? "API OFFLINE" : meta.health?.status ?? "…"}
            </span>
          </div>
        </div>
      </header>

      <main className="min-h-screen pt-16">
        <div className="mx-auto px-6 py-8 space-y-8" style={{ maxWidth: "80rem" }}>
          <Outlet />
        </div>
      </main>

      <footer
        className="border-t py-6"
        style={{ background: "var(--surface-container-lowest)", borderColor: "var(--surface-container)" }}
      >
        <div className="mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-3" style={{ maxWidth: "80rem" }}>
          <div className="flex items-center gap-2 text-secondary" style={{ fontSize: 13 }}>
            <span className="app-headline-sm" style={{ fontSize: 13 }}>
              DocFetch
            </span>
            <span>— authorized security testing. Findings reflect observed server behavior.</span>
          </div>
          <div className="flex items-center gap-4 app-label-sm text-secondary">
            <NavLink to="/settings" className="hover:text-primary">
              API Status
            </NavLink>
            <span style={{ textTransform: "none" }}>
              v{meta.version?.version ?? "…"} · {meta.version?.app_env ?? ""}
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}