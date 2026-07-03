import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { SimResult } from '../types';
import { adapt } from '../lib/api';

const AXIS = { stroke: '#94a3b8', fontSize: 11 };

// Renders whatever series the ACTIVE sweep returned (fix #6) via the adapter.
export function GraphPanel({ title, data }: { title: string; data: SimResult }) {
  const c = adapt(data);
  return (
    <div className="rounded-xl bg-slate-900/70 border border-zinc-800 p-4">
      <h3 className="text-lg font-semibold text-slate-100 mb-3">{title}</h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={c.rows} margin={{ top: 8, right: 16, bottom: 18, left: 8 }}>
            <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
            <XAxis
              dataKey="x"
              tick={AXIS}
              stroke="#334155"
              type={c.categorical ? 'category' : 'number'}
              domain={c.categorical ? undefined : ['auto', 'auto']}
              label={{
                value: c.xLabel,
                position: 'insideBottom',
                offset: -8,
                fill: '#64748b',
                fontSize: 11,
              }}
            />
            <YAxis
              tick={AXIS}
              stroke="#334155"
              scale={c.logY ? 'log' : 'linear'}
              domain={c.logY ? ['dataMin', 'dataMax'] : ['auto', 'auto']}
              allowDataOverflow={false}
              width={70}
              tickFormatter={(v: number) =>
                c.logY ? v.toExponential(0) : String(v)
              }
              label={{
                value: c.yLabel,
                angle: -90,
                position: 'insideLeft',
                fill: '#64748b',
                fontSize: 11,
              }}
            />
            <Tooltip
              contentStyle={{
                background: '#0f172a',
                border: '1px solid #27272a',
                borderRadius: 8,
                fontSize: 12,
              }}
              labelStyle={{ color: '#94a3b8' }}
            />
            <Legend wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
            {c.lines.map((l) => (
              <Line
                key={l.key}
                type="monotone"
                dataKey={l.key}
                name={l.key}
                stroke={l.color}
                strokeWidth={2}
                dot={false}
                isAnimationActive
                animationDuration={300}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
