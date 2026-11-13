import { PanelLeftClose, PanelLeftOpen, X } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import type { NavItem } from "./nav";

interface SidebarProps {
  items: NavItem[];
  collapsed: boolean;
  mobileOpen: boolean;
  onToggleCollapsed: () => void;
  onCloseMobile: () => void;
}

export function Sidebar({ items, collapsed, mobileOpen, onToggleCollapsed, onCloseMobile }: SidebarProps) {
  const { pathname } = useLocation();
  const width = collapsed ? "lg:w-16" : "lg:w-60";

  return (
    <>
      {mobileOpen && (
        <button
          aria-label="Close navigation"
          className="no-print fixed inset-0 z-30 bg-ink/30 lg:hidden"
          onClick={onCloseMobile}
        />
      )}
      <aside
        className={`no-print fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-surface transition-transform lg:translate-x-0 ${width} ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-14 items-center justify-between border-b border-line px-4">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <span
              aria-hidden
              className="grid size-7 shrink-0 place-items-center rounded-md bg-brand text-sm font-bold text-white"
            >
              G
            </span>
            <div className={`leading-tight ${collapsed ? "lg:hidden" : ""}`}>
              <p className="text-sm font-semibold text-ink">GharMoolya</p>
              <p className="text-[11px] text-muted">by Neural Knights</p>
            </div>
          </div>
          <button
            aria-label="Close navigation"
            className="rounded p-1 text-muted hover:bg-hover lg:hidden"
            onClick={onCloseMobile}
          >
            <X className="size-5" />
          </button>
        </div>

        <nav aria-label="Primary" className="flex-1 space-y-1 p-2.5">
          {items.map(({ to, label, icon: Icon, matchPrefix }) => {
            const active = matchPrefix ? pathname.startsWith(matchPrefix) : pathname === to;
            return (
              <NavLink
                key={label}
                to={to}
                title={collapsed ? label : undefined}
                onClick={onCloseMobile}
                aria-current={active ? "page" : undefined}
                className={`relative flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors ${
                  active ? "bg-hover text-ink" : "text-muted hover:bg-hover hover:text-ink"
                } ${collapsed ? "lg:justify-center lg:px-0" : ""}`}
              >
                {active && <span aria-hidden className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-brand" />}
                <Icon aria-hidden className="size-[18px] shrink-0" />
                <span className={collapsed ? "lg:sr-only" : ""}>{label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="hidden border-t border-line p-2.5 lg:block">
          <button
            onClick={onToggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={`flex h-9 w-full cursor-pointer items-center gap-3 rounded-md px-3 text-sm text-muted hover:bg-hover hover:text-ink ${
              collapsed ? "justify-center px-0" : ""
            }`}
          >
            {collapsed ? <PanelLeftOpen className="size-[18px]" /> : <PanelLeftClose className="size-[18px]" />}
            {!collapsed && "Collapse"}
          </button>
        </div>
      </aside>
    </>
  );
}
