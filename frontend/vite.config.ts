// Vite: dev server, bundler, and the Vitest configuration. Spec 002.
import babel from '@rolldown/plugin-babel'
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import type { Plugin } from 'vite'
import { defineConfig } from 'vitest/config'

// P12: dist/bundle-report.json lists every chunk with the module ids bundled into it, which the
// Vite manifest does not carry. scripts/check-bundle.mjs reads it (AC 12).
function bundleReport(): Plugin {
  return {
    name: 'bundle-report',
    apply: 'build',
    generateBundle(_options, bundle) {
      const chunks = Object.values(bundle).flatMap((output) =>
        output.type === 'chunk'
          ? [
              {
                fileName: output.fileName,
                isEntry: output.isEntry,
                imports: output.imports,
                dynamicImports: output.dynamicImports,
                modules: output.moduleIds,
              },
            ]
          : [],
      )
      this.emitFile({ type: 'asset', fileName: 'bundle-report.json', source: JSON.stringify(chunks, null, 2) })
    },
  }
}

// FR-API-05: the browser calls `/api/*`; in development Vite forwards it to the backend with
// the prefix stripped, so the backend needs no CORS configuration. P8: `127.0.0.1:8000` is the
// backend README's `uvicorn` default.
const backendUrl = process.env['VITE_BACKEND_URL'] ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), babel({ presets: [reactCompilerPreset()] }), bundleReport()],
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
