import { useState, useEffect, useRef } from "react";

/**
 * Animated counter that counts up from 0 to the target value.
 * Optionally formats the number (currency, percentage, etc.)
 */
export default function AnimatedCounter({ value, duration = 1200, formatter, prefix = "", suffix = "" }) {
  const [display, setDisplay] = useState(0);
  const startTime = useRef(null);
  const rafId = useRef(null);

  useEffect(() => {
    if (typeof value !== "number" || isNaN(value)) return;

    const target = value;
    startTime.current = performance.now();

    const animate = (now) => {
      const elapsed = now - startTime.current;
      const progress = Math.min(elapsed / duration, 1);

      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = eased * target;

      setDisplay(current);

      if (progress < 1) {
        rafId.current = requestAnimationFrame(animate);
      }
    };

    rafId.current = requestAnimationFrame(animate);

    return () => {
      if (rafId.current) cancelAnimationFrame(rafId.current);
    };
  }, [value, duration]);

  const formatted = formatter
    ? formatter(display)
    : Number.isInteger(value)
      ? Math.round(display).toLocaleString()
      : display.toFixed(1);

  return (
    <span>
      {prefix}{formatted}{suffix}
    </span>
  );
}
