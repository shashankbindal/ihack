import { useMemo, useState } from "react";
import { Outlet } from "react-router-dom";
import { useStaticData } from "../../hooks/useStaticData";
import { listStoredReports } from "../../lib/store";
import type { QueueRow } from "../../lib/types";
import { Footer } from "./Footer";
import { buildNav } from "./nav";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

const COLLAPSED_KEY = "gharmoolya:sidebar-collapsed";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [mobileOpen, setMobileOpen] = useState(false);
  const queue = useStaticData<QueueRow[]>("queue.json").data;
  const reportId = listStoredReports()[0]?.id ?? queue?.[0]?.listing_id ?? null;
  const items = useMemo(() => buildNav(reportId), [reportId]);

  const toggleCollapsed = () => {
    setCollapsed((current) => {
      try {
        localStorage.setItem(COLLAPSED_KEY, current ? "0" : "1");
      } catch {
        // The preference is cosmetic; ignore blocked storage.
      }
      return !current;
    });
  };

  return (
    <div className="min-h-screen">
      <Sidebar
        items={items}
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onToggleCollapsed={toggleCollapsed}
        onCloseMobile={() => setMobileOpen(false)}
      />
      <div className={`print-full transition-[padding] ${collapsed ? "lg:pl-16" : "lg:pl-60"}`}>
        <TopBar onOpenMobile={() => setMobileOpen(true)} />
        <main className="mx-auto max-w-[1360px] px-4 py-6 sm:px-6 lg:py-8">
          <Outlet />
          <Footer />
        </main>
      </div>
    </div>
  );
}
