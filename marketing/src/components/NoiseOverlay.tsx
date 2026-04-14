export function NoiseOverlay() {
  // Inline SVG noise — no external fetch, no JS
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='200' height='200'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0.08 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>`;
  const encoded = svg.replace(/#/g, "%23");
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-0 opacity-[0.035] mix-blend-screen"
      style={{
        backgroundImage: `url("data:image/svg+xml;utf8,${encoded}")`,
        backgroundSize: "200px 200px",
      }}
    />
  );
}
