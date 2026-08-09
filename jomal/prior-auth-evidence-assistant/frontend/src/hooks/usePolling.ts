/**
 * usePolling hook — T067
 * Polls a given async function at a configurable interval (default 15s).
 * Updates state reactively. No WebSocket infrastructure in v1 (per spec).
 */
import { useEffect, useRef, useCallback } from 'react';

interface UsePollingOptions {
  interval?: number; // ms, default 15000
  enabled?: boolean;
}

export function usePolling(
  fn: () => Promise<void>,
  options: UsePollingOptions = {}
) {
  const { interval = 15000, enabled = true } = options;
  const savedFn = useRef(fn);

  useEffect(() => {
    savedFn.current = fn;
  }, [fn]);

  useEffect(() => {
    if (!enabled) return;

    // Run immediately on mount
    savedFn.current().catch(() => {});

    const id = setInterval(() => {
      savedFn.current().catch(() => {});
    }, interval);

    return () => clearInterval(id);
  }, [enabled, interval]);
}
