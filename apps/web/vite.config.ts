/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  server: {
    port: 5173,
    // Proxy /api and /auth to the BFF so that the SPA's cookie lives on the same
    // origin the user's browser sees (localhost:5173), and every API hop goes
    // through the BFF (which enforces session, CSRF, and attaches the Bearer
    // to upstream calls). The BFF re-proxies /api/* to the api role.
    proxy: {
      '/api': { target: 'http://localhost:8080', changeOrigin: false },
      '/auth': { target: 'http://localhost:8080', changeOrigin: false },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['node_modules', 'dist', 'tests/e2e/**'],
  },
  base: process.env.VITE_BASE_PATH ?? './',
});
