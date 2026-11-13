import { FileText, LayoutDashboard, Map, ShieldCheck, SquarePen, type LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  matchPrefix?: string;
}

export const buildNav = (reportId: string | null): NavItem[] => [
  { to: "/dashboard", label: "Executive overview", icon: LayoutDashboard },
  { to: "/evaluate", label: "New valuation", icon: SquarePen },
  {
    to: reportId ? `/report/${reportId}` : "/dashboard",
    label: "Valuation report",
    icon: FileText,
    matchPrefix: "/report",
  },
  { to: "/market-explorer", label: "Market explorer", icon: Map },
  { to: "/model-audit", label: "Model audit", icon: ShieldCheck },
];
