// ########################################################################
// #                       frontend/vite.config.ts                        #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           Build, dev-server and test settings: React, the  #
// #                     API proxy to port 8000, and jsdom for tests.     #
// ########################################################################
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// log.debug('Exports the build, dev-server and test settings')
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } },
  },
  build: { outDir: 'dist', emptyOutDir: true, sourcemap: false },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
  },
});
