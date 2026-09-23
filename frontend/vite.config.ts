// Vite: dev server, bundler, and the Vitest configuration. Spec 002.
import babel from '@rolldown/plugin-babel'
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

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
  test: {
    // Components run in jsdom; the Node-run tests opt out with `@vitest-environment node`.
    environment: 'jsdom',
    setupFiles: ['./test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}', 'test/**/*.test.{ts,tsx}'],
    // NFR-04: component tests never reach the network; an unhandled request fails the test.
    restoreMocks: true,
  },
})
