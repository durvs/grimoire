// Root layout do grupo (redirect): a página `/` só redireciona server-side
// para /en ou /pt, então este html nunca chega a pintar.
export default function RedirectLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
