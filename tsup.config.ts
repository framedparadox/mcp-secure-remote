import { defineConfig } from 'tsup'

export default defineConfig({
  entry: ['src/proxy.ts', 'src/client.ts'],
  format: ['esm'],
  target: 'node18',
  dts: true,
  sourcemap: true,
  clean: true,
  splitting: false,
  shims: true,
  banner: {
    js: '#!/usr/bin/env node',
  },
})
