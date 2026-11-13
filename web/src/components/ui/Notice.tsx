import { Info, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

interface NoticeProps {
  children: ReactNode;
  tone?: "info" | "warn";
  title?: string;
}

export function Notice({ children, tone = "info", title }: NoticeProps) {
  const Icon = tone === "warn" ? TriangleAlert : Info;
  const colour = tone === "warn" ? "border-warn/30 bg-warn-tint" : "border-line bg-surface";
  return (
    <div role={tone === "warn" ? "alert" : "note"} className={`flex gap-3 rounded-lg border p-4 text-sm ${colour}`}>
      <Icon aria-hidden className={`mt-0.5 size-4 shrink-0 ${tone === "warn" ? "text-warn-ink" : "text-muted"}`} />
      <div className="leading-relaxed text-ink">
        {title && <p className="font-semibold">{title}</p>}
        <div className={title ? "mt-0.5 text-muted" : ""}>{children}</div>
      </div>
    </div>
  );
}

export function NotBuilt({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-canvas p-4">
      <p className="text-sm font-semibold text-ink">{title}</p>
      <p className="mt-1 text-xs leading-relaxed text-muted">{children}</p>
    </div>
  );
}
