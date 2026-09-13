import { defineConfig } from 'vite';

export default defineConfig({
  server: { proxy: { '/api': 'http://127.0.0.1:6006' } },
  build: { target: 'es2022', sourcemap: false },
});
