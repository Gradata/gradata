import '@testing-library/jest-dom'
import { vi } from 'vitest'
import * as React from 'react'

// Recharts' ResponsiveContainer uses getBoundingClientRect which returns 0 in
// jsdom, collapsing charts to width/height -1 and skipping render. Mock it with
// a fixed-size wrapper so Recharts actually renders SVG (required for tests
// that assert on chart-level custom SVG attributes like [data-graduation-marker]).
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>()
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
      React.createElement(
        'div',
        { style: { width: 800, height: 400 } },
        React.createElement(
          actual.ResponsiveContainer,
          { width: 800, height: 400 },
          children,
        ),
      ),
  }
})
