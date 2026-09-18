import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      tone: {
        neutral: "border-line bg-elevated text-muted",
        brand: "border-iris/30 bg-iris/10 text-iris-soft",
        good: "border-good/30 bg-good/10 text-good",
        fair: "border-fair/30 bg-fair/10 text-fair",
        poor: "border-poor/30 bg-poor/10 text-poor",
      },
    },
    defaultVariants: { tone: "neutral" },
  }
);

export function Badge({
  className,
  tone,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
