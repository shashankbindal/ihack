import { Menu } from "lucide-react";
import { QuickSearch } from "./QuickSearch";

export function TopBar({ onOpenMobile }: { onOpenMobile: () => void }) {
  return (
    <header className="no-print sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-surface px-4 sm:px-6">
      <button
        aria-label="Open navigation"
        className="-ml-1 rounded p-1.5 text-ink hover:bg-hover lg:hidden"
        onClick={onOpenMobile}
      >
        <Menu className="size-5" />
      </button>
      <QuickSearch />
      <div className="ml-auto flex shrink-0 items-center gap-2 rounded-md border border-line bg-canvas px-2.5 py-1.5 text-xs font-medium text-muted">
        <span aria-hidden className="size-1.5 rounded-full bg-muted" />
        Demo session
      </div>
    </header>
  );
}
