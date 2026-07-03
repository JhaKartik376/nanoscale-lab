/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        drive: '#22d3ee',   // cyan-400  - on-current
        quantum: '#34d399', // emerald-400 - tunneling / wave
        leak: '#fbbf24',    // amber-400 - subthreshold
        danger: '#ef4444',  // red-500   - gate leakage / breakdown
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
};
