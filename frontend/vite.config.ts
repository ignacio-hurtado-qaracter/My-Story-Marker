// Vite: dev server, bundler, and (from plan step 4) the Vitest configuration. Spec 002.
import babel from '@rolldown/plugin-babel'
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// FR-API-05: the browser calls `/api/*`; in development Vite forwards it to the backend with
// the prefix stripped, so the backend needs no CORS configuration. P8: `127.0.0.1:8000` is the
// backend README's `uvicorn` default.
const backendUrl = process.env['VITE_BACKEND_URL'] ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), babel({ presets: [reactCompilerPreset()] })],
  server: {
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
