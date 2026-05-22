import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/static/lhexia-logo-3d/',
  server: { port: 5174, strictPort: true },
});
