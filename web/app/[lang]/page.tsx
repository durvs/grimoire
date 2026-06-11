export default async function Landing({
  params,
}: {
  params: Promise<{ lang: string }>;
}) {
  const { lang } = await params;
  return <main>{lang}</main>;
}
