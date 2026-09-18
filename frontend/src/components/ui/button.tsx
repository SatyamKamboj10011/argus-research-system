import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-200 disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary:
          "rounded-full bg-[linear-gradient(to_top,#cfdef6_20%,#fafafa_80%)] text-[#09090b] font-semibold shadow-[0_4px_24px_-6px_rgba(255,255,255,0.35)] hover:brightness-105 hover:shadow-[0_6px_30px_-6px_rgba(255,255,255,0.5)] active:scale-[0.98]",
        secondary:
          "bg-elevated text-ink border border-line hover:border-line-bright hover:bg-raised active:scale-[0.98]",
        ghost: "text-muted hover:text-ink hover:bg-elevated",
        outline:
          "border border-line text-ink hover:border-iris/50 hover:bg-iris/5 active:scale-[0.98]",
        danger: "bg-poor/15 text-poor border border-poor/30 hover:bg-poor/25",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-4",
        lg: "h-12 px-6 text-base",
        icon: "size-9",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
    );
  }
);
Button.displayName = "Button";

export { buttonVariants };
