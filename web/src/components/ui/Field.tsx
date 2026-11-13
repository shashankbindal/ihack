import type { InputHTMLAttributes, ReactNode } from "react";
import { formatCompactInr } from "../../lib/format";

export const CONTROL_CLASS =
  "h-10 w-full rounded-md border border-line bg-surface px-3 text-sm text-ink placeholder:text-muted hover:border-muted/60 disabled:cursor-not-allowed disabled:bg-canvas disabled:text-muted";

interface FieldProps {
  label: string;
  htmlFor: string;
  hint?: ReactNode;
  tag?: string;
  children: ReactNode;
}

export function Field({ label, htmlFor, hint, tag, children }: FieldProps) {
  return (
    <div>
      <div className="mb-1.5 flex h-6 items-center justify-between gap-2">
        <label htmlFor={htmlFor} className="text-xs font-semibold text-ink">
          {label}
        </label>
        {tag && (
          <span className="whitespace-nowrap rounded border border-line bg-canvas px-1.5 py-0.5 text-[10px] font-medium text-muted">
            {tag}
          </span>
        )}
      </div>
      {children}
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </div>
  );
}

interface MoneyFieldProps {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  hint?: string;
  tag?: string;
}

export function MoneyField({ label, value, onChange, hint, tag }: MoneyFieldProps) {
  const id = `money-${label.replace(/\W+/g, "-").toLowerCase()}`;
  return (
    <Field
      label={label}
      htmlFor={id}
      tag={tag}
      hint={value !== null ? `${formatCompactInr(value)}${hint ? `. ${hint}` : ""}` : hint}
    >
      <div className="relative">
        <span aria-hidden className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted">
          ₹
        </span>
        <input
          id={id}
          inputMode="numeric"
          className={`${CONTROL_CLASS} num pl-7`}
          value={value === null ? "" : new Intl.NumberFormat("en-IN").format(value)}
          placeholder="Optional"
          onChange={(event) => {
            const digits = event.target.value.replace(/\D/g, "");
            onChange(digits ? Number(digits) : null);
          }}
        />
      </div>
    </Field>
  );
}

export function NumberInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input type="number" className={`${CONTROL_CLASS} num`} {...props} />;
}
