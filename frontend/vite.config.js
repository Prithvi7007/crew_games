import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: resolve(here, '../app/static/react'),
    emptyOutDir: false,
    sourcemap: false,
    cssCodeSplit: false,
    rollupOptions: {
      input: resolve(here, 'src/trivia/main.jsx'),
      output: {
        entryFileNames: 'trivia.js',
        assetFileNames: (assetInfo) => assetInfo.name?.endsWith('.css') ? 'trivia.css' : 'assets/[name]-[hash][extname]',
      },
    },
  },
});
