import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { Evaluate } from "./pages/Evaluate";
import { ModelAudit } from "./pages/ModelAudit";
import { Report } from "./pages/Report";

const Dashboard = lazy(() => import("./pages/Dashboard").then((m) => ({ default: m.Dashboard })));
const MarketExplorer = lazy(() => import("./pages/MarketExplorer").then((m) => ({ default: m.MarketExplorer })));

export default function App() {
  return (
    <Suspense fallback={<p role="status" className="p-6 text-sm text-muted">Loading</p>}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/evaluate" element={<Evaluate />} />
          <Route path="/report/:id" element={<Report />} />
          <Route path="/market-explorer" element={<MarketExplorer />} />
          <Route path="/model-audit" element={<ModelAudit />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
