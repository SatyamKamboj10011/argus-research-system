import * as React from "react";
import { useReducedMotion } from "motion/react";
import { cn } from "@/lib/utils";

/**
 * Procedural animated backgrounds.
 *
 * The reference this was briefed against ships video loops. Video is the wrong
 * tool here: a few megabytes of photographic footage behind a research report
 * costs load time and competes with the text. These draw the same sense of
 * movement from a few kilobytes of code, and every one of them stops dead under
 * `prefers-reduced-motion`.
 */

/** Pause work when the tab is hidden or the element scrolls out of view. */
function useIsVisible(ref: React.RefObject<HTMLElement | null>) {
  const [visible, setVisible] = React.useState(true);

  React.useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;

    let onScreen = true;
    const update = () => setVisible(onScreen && !document.hidden);

    const observer = new IntersectionObserver(([entry]) => {
      onScreen = entry.isIntersecting;
      update();
    });
    observer.observe(node);
    document.addEventListener("visibilitychange", update);

    return () => {
      observer.disconnect();
      document.removeEventListener("visibilitychange", update);
    };
  }, [ref]);

  return visible;
}

interface Blob {
  hue: [number, number, number];
  x: number;
  y: number;
  radius: number;
  speedX: number;
  speedY: number;
  phase: number;
}

const PALETTE: Array<[number, number, number]> = [
  [208, 178, 255], // lavender
  [255, 238, 216], // cream
  [232, 64, 13], // ember
  [167, 139, 250], // iris
];

/**
 * A drifting mesh gradient.
 *
 * Drawn on a deliberately tiny canvas (a couple of hundred pixels) and scaled up
 * by CSS. The browser's own smoothing does the blurring for free, which keeps
 * this at a fraction of the cost of a full-resolution canvas blur.
 */
export function MeshGradient({
  className,
  intensity = 0.42,
  blobs: blobCount = 4,
}: {
  className?: string;
  intensity?: number;
  blobs?: number;
}) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const wrapRef = React.useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const visible = useIsVisible(wrapRef);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext("2d");
    if (!ctx) return undefined;

    const W = 220;
    const H = 150;
    canvas.width = W;
    canvas.height = H;

    const blobs: Blob[] = Array.from({ length: blobCount }, (_, i) => ({
      hue: PALETTE[i % PALETTE.length],
      x: Math.random() * W,
      y: Math.random() * H,
      radius: (0.34 + Math.random() * 0.3) * W,
      speedX: (Math.random() - 0.5) * 0.09,
      speedY: (Math.random() - 0.5) * 0.07,
      phase: Math.random() * Math.PI * 2,
    }));

    const paint = (time: number) => {
      ctx.clearRect(0, 0, W, H);
      ctx.globalCompositeOperation = "lighter";

      for (const blob of blobs) {
        // A slow breathing radius keeps the field from looking like rigid
        // objects sliding past each other.
        const pulse = 1 + Math.sin(time * 0.0004 + blob.phase) * 0.18;
        const radius = blob.radius * pulse;
        const gradient = ctx.createRadialGradient(blob.x, blob.y, 0, blob.x, blob.y, radius);
        const [r, g, b] = blob.hue;
        gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${0.5 * intensity})`);
        gradient.addColorStop(0.5, `rgba(${r}, ${g}, ${b}, ${0.16 * intensity})`);
        gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(blob.x, blob.y, radius, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.globalCompositeOperation = "source-over";
    };

    if (reduce) {
      paint(0);
      return undefined;
    }

    let frame = 0;
    let last = performance.now();

    const step = (now: number) => {
      const delta = Math.min(now - last, 48);
      last = now;

      for (const blob of blobs) {
        blob.x += blob.speedX * delta * 0.06;
        blob.y += blob.speedY * delta * 0.06;
        if (blob.x < -blob.radius) blob.x = W + blob.radius;
        if (blob.x > W + blob.radius) blob.x = -blob.radius;
        if (blob.y < -blob.radius) blob.y = H + blob.radius;
        if (blob.y > H + blob.radius) blob.y = -blob.radius;
      }

      paint(now);
      frame = requestAnimationFrame(step);
    };

    if (visible) {
      last = performance.now();
      frame = requestAnimationFrame(step);
    } else {
      paint(performance.now());
    }

    return () => cancelAnimationFrame(frame);
  }, [blobCount, intensity, reduce, visible]);

  return (
    <div
      ref={wrapRef}
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
    >
      <canvas
        ref={canvasRef}
        className="size-full opacity-45"
        style={{
          filter: "blur(40px) saturate(115%)",
          transform: "scale(1.3)",
          // Weighted to the top so the colour reads as light falling into the
          // page, and the content below keeps a near-black ground to sit on.
          maskImage: "linear-gradient(to bottom, #000 0%, rgba(0,0,0,0.55) 42%, transparent 78%)",
        }}
      />
    </div>
  );
}

/**
 * Slow light rays raking across the top of the page.
 *
 * Pure CSS: three skewed gradient bars on long, offset loops.
 */
export function Beams({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
      style={{ maskImage: "linear-gradient(to bottom, #000 0%, transparent 75%)" }}
    >
      {[
        { left: "12%", delay: "0s", duration: "17s", width: "16rem" },
        { left: "46%", delay: "-6s", duration: "22s", width: "11rem" },
        { left: "74%", delay: "-12s", duration: "19s", width: "14rem" },
      ].map((beam) => (
        <div
          key={beam.left}
          className="absolute -top-1/2 h-[200%] origin-top animate-[beam_var(--dur)_ease-in-out_infinite] motion-reduce:animate-none"
          style={
            {
              left: beam.left,
              width: beam.width,
              animationDelay: beam.delay,
              "--dur": beam.duration,
              background:
                "linear-gradient(to bottom, color-mix(in oklab, var(--color-lavender) 12%, transparent), transparent 65%)",
              filter: "blur(26px)",
              transform: "rotate(14deg)",
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}

interface Mote {
  x: number;
  y: number;
  z: number;
  size: number;
  drift: number;
}

/**
 * Drifting dust motes with a little parallax toward the pointer.
 *
 * Depth (`z`) drives size, opacity and how far a mote shifts with the cursor, so
 * the field reads as space rather than as a flat sheet of dots.
 */
export function ParticleField({
  className,
  count = 60,
}: {
  className?: string;
  count?: number;
}) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const wrapRef = React.useRef<HTMLDivElement>(null);
  const pointer = React.useRef({ x: 0, y: 0 });
  const reduce = useReducedMotion();
  const visible = useIsVisible(wrapRef);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return undefined;
    const ctx = canvas.getContext("2d");
    if (!ctx) return undefined;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let width = 0;
    let height = 0;
    let motes: Mote[] = [];

    const resize = () => {
      const rect = wrap.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      canvas.width = Math.max(1, Math.floor(width * dpr));
      canvas.height = Math.max(1, Math.floor(height * dpr));
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      motes = Array.from({ length: count }, () => {
        const z = 0.25 + Math.random() * 0.75;
        return {
          x: Math.random() * width,
          y: Math.random() * height,
          z,
          size: z * 1.6,
          drift: (0.08 + Math.random() * 0.16) * z,
        };
      });
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(wrap);

    const onPointer = (event: PointerEvent) => {
      const rect = wrap.getBoundingClientRect();
      pointer.current = {
        x: (event.clientX - rect.left) / rect.width - 0.5,
        y: (event.clientY - rect.top) / rect.height - 0.5,
      };
    };
    window.addEventListener("pointermove", onPointer, { passive: true });

    const paint = () => {
      ctx.clearRect(0, 0, width, height);
      for (const mote of motes) {
        const px = mote.x + pointer.current.x * 26 * mote.z;
        const py = mote.y + pointer.current.y * 18 * mote.z;
        ctx.globalAlpha = 0.1 + mote.z * 0.34;
        ctx.fillStyle = "#d8d2ff";
        ctx.beginPath();
        ctx.arc(px, py, mote.size, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    };

    if (reduce) {
      paint();
      observer.disconnect();
      window.removeEventListener("pointermove", onPointer);
      return () => observer.disconnect();
    }

    let frame = 0;
    const step = () => {
      for (const mote of motes) {
        mote.y -= mote.drift;
        if (mote.y < -4) {
          mote.y = height + 4;
          mote.x = Math.random() * width;
        }
      }
      paint();
      frame = requestAnimationFrame(step);
    };

    if (visible) frame = requestAnimationFrame(step);
    else paint();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("pointermove", onPointer);
    };
  }, [count, reduce, visible]);

  return (
    <div
      ref={wrapRef}
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
    >
      <canvas ref={canvasRef} className="size-full" />
    </div>
  );
}

/** A grid that fades toward the horizon, giving the flat ground some depth. */
export function PerspectiveGrid({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
      style={{
        backgroundImage:
          "linear-gradient(to right, var(--color-line) 1px, transparent 1px), linear-gradient(to bottom, var(--color-line) 1px, transparent 1px)",
        backgroundSize: "60px 60px",
        maskImage: "radial-gradient(ellipse 75% 55% at 50% 0%, #000 35%, transparent 100%)",
        opacity: 0.45,
      }}
    />
  );
}

/** Film grain, so large flat areas of dark do not band on cheap panels. */
export function Grain({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn("pointer-events-none absolute inset-0 grain-overlay", className)} />
  );
}

/** The hero's full background stack, composed in one place. */
export function HeroBackdrop() {
  return (
    <>
      <MeshGradient />
      <Beams />
      <ParticleField />
      <PerspectiveGrid />
      {/* Holds the colour back so text keeps its contrast against the ground. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-base/45"
        style={{
          maskImage: "linear-gradient(to bottom, rgba(0,0,0,0.5) 0%, #000 55%)",
        }}
      />
      <Grain />
    </>
  );
}
