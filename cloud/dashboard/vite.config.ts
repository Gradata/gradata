import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { sentryVitePlugin } from '@sentry/vite-plugin'

// Upload source maps to Sentry only when auth token is present.
// Without the plugin, prod stack traces are minified and useless.
// SENTRY_AUTH_TOKEN is a build-time secret (set in Cloudflare Pages env).
const sentryAuthToken = process.env.SENTRY_AUTH_TOKEN
const sentryOrg = process.env.SENTRY_ORG ?? 'gradata'
const sentryProject = process.env.SENTRY_PROJECT ?? 'gradata-dashboard'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    ...(sentryAuthToken
      ? [
          sentryVitePlugin({
            org: sentryOrg,
            project: sentryProject,
            authToken: sentryAuthToken,
            // Delete source maps after upload so they're not served to browsers
            sourcemaps: { filesToDeleteAfterUpload: '**/*.map' },
          }),
        ]
      : []),
  ],
  build: {
    // Generate source maps so Sentry can symbolicate — deleted after upload
    sourcemap: !!sentryAuthToken,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
