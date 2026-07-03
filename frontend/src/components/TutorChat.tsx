import { useState } from 'react';
import { fetchChat } from '../lib/api';

// Surfaces the backend /chat tutor. Grounded in the current sim numbers; when
// no ANTHROPIC_API_KEY is set the backend answers via the rule engine.
export function TutorChat({
  node,
  mode,
  material,
}: {
  node: string;
  mode: string;
  material: string;
}) {
  const [log, setLog] = useState<{ q: string; a: string; source: string }[]>([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);

  async function ask() {
    const question = q.trim();
    if (!question || busy) return;
    setBusy(true);
    try {
      const { answer, source } = await fetchChat(node, mode, material, question);
      setLog((l) => [...l, { q: question, a: answer, source }]);
      setQ('');
    } catch (e) {
      setLog((l) => [...l, { q: question, a: `error: ${e}`, source: 'error' }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl bg-slate-900/70 border border-zinc-800 p-4">
      <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">
        Ask the tutor
      </div>
      <div className="space-y-3 max-h-52 overflow-auto mb-3">
        {log.length === 0 && (
          <p className="text-xs text-slate-500">
            e.g. “why does {node} leak?” or “what would graphene change?”
          </p>
        )}
        {log.map((m, i) => (
          <div key={i} className="text-sm">
            <p className="text-slate-400">🙋 {m.q}</p>
            <p className="text-slate-200 mt-0.5">
              🎓 {m.a}
              {m.source === 'rule-based-fallback' && (
                <span className="ml-1 text-[10px] text-slate-500">
                  (offline: rule-based)
                </span>
              )}
            </p>
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && ask()}
          placeholder={`Ask about the ${node} device…`}
          disabled={busy}
          className="flex-1 bg-slate-950 border border-zinc-800 rounded-md px-2.5 py-1.5 text-sm text-slate-100 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-cyan-400/40"
        />
        <button
          onClick={ask}
          disabled={busy}
          className="px-3 py-1.5 text-sm rounded-md bg-cyan-500/15 text-cyan-300 ring-1 ring-cyan-400/40 disabled:opacity-50"
        >
          {busy ? '…' : 'Ask'}
        </button>
      </div>
    </div>
  );
}
