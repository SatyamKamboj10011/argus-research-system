import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";

export const Tabs = TabsPrimitive.Root;

export const TabsList = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn(
      "flex w-full items-center gap-1 overflow-x-auto border-b border-line pb-px [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
      className
    )}
    {...props}
  />
));
TabsList.displayName = "TabsList";

/**
 * A tab whose active underline is a single shared element that slides between
 * triggers, rather than a border toggled on and off per tab.
 */
export const TabsTrigger = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger> & {
    active?: boolean;
    indicatorId?: string;
  }
>(({ className, children, active, indicatorId = "tab-indicator", ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "relative shrink-0 px-3 py-2.5 text-sm font-medium transition-colors duration-200 outline-none",
      active ? "text-ink" : "text-faint hover:text-muted",
      className
    )}
    {...props}
  >
    <span className="relative z-10 flex items-center gap-1.5">{children}</span>
    {active && (
      <motion.span
        layoutId={indicatorId}
        className="absolute inset-x-1 -bottom-px h-0.5 rounded-full bg-linear-to-r from-iris to-cyan"
        transition={{ type: "spring", stiffness: 380, damping: 32 }}
      />
    )}
  </TabsPrimitive.Trigger>
));
TabsTrigger.displayName = "TabsTrigger";

export const TabsContent = TabsPrimitive.Content;
