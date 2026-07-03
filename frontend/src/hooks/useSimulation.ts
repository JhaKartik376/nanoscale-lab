import { useEffect, useRef, useState } from 'react';
import type { SimState, SimResult } from '../types';
import { fetchSimulate } from '../lib/api';

const DEBOUNCE_MS = 250;

export function useSimulation(sim: SimState) {
  const [data, setData] = useState<SimResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const ctrl = useRef<AbortController | null>(null);

  useEffect(() => {
    clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      ctrl.current?.abort();
      ctrl.current = new AbortController();
      setLoading(true);
      setError(null);
      fetchSimulate(sim, ctrl.current.signal)
        .then((json) => setData(json))
        .catch((e) => {
          if (e.name !== 'AbortError') setError(String(e.message ?? e));
        })
        .finally(() => setLoading(false));
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sim.node, sim.mode, sim.sweep, sim.material, sim.accuracy, sim.vd, sim.vg]);

  return { data, loading, error };
}
