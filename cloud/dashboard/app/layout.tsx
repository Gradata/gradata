import type { Metadata } from 'next'
import './globals.css'
import { AuthProvider } from '@/components/providers/AuthProvider'
import { NoiseOverlay } from '@/components/layout/NoiseOverlay'

export const metadata: Metadata = {
  title: 'Gradata',
  description: 'AI that learns the corrections you keep making',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        {/* Fonts loaded via CSS rather than next/font — static export + turbopack path issue */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
        />
      </head>
      <body>
        <NoiseOverlay />
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  )
}
