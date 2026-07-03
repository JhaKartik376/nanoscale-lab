import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The frontend talks to the FastAPI backend. Two options, both handled:
//  1) default: src/lib/api.ts uses VITE_API_URL (default http://localhost:8000);
//     CORS on the backend already allows http://localhost:5173.
//  2) fallback proxy below: if you prefer same-origin, set VITE_API_URL=""  and
//     these paths are proxied to the backend so no CORS is involved. (fix #7)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/simulate': 'http://localhost:8000',
      '/graph-data': 'http://localhost:8000',
      '/explain': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/nodes': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
});
