import type { ReactNode } from "react";

export function Table({ children, label }: { children: ReactNode; label: string }) {
  return (
    <div className="relative overflow-x-auto">
      <table aria-label={label} className="w-full border-collapse text-left text-sm">
        {children}
      </table>
    </div>
  );
}

interface CellProps {
  children?: ReactNode;
  numeric?: boolean;
  className?: string;
}

export function Th({ children, numeric = false, className = "" }: CellProps) {
  return (
    <th
      scope="col"
      className={`whitespace-nowrap border-b border-line bg-canvas px-4 py-2.5 text-xs font-semibold text-muted ${
        numeric ? "text-right" : ""
      } ${className}`}
    >
      {children}
    </th>
  );
}

export function Td({ children, numeric = false, className = "" }: CellProps) {
  return (
    <td
      className={`border-b border-line px-4 py-3 align-middle ${numeric ? "num text-right" : ""} ${className}`}
    >
      {children}
    </td>
  );
}
