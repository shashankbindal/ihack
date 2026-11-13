import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary";

const VARIANTS: Record<Variant, string> = {
  primary: "border-brand bg-brand text-white hover:bg-brand-dark hover:border-brand-dark",
  secondary: "border-line bg-surface text-ink hover:bg-hover",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export function Button({ variant = "secondary", className = "", ...props }: ButtonProps) {
  return (
    <button
      type="button"
      className={`inline-flex h-9 cursor-pointer items-center justify-center gap-2 rounded-md border px-3.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}
