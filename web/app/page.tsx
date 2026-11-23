import ProviderGate from "../components/provider-gate";
export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ url?: string }>;
}) {
  const { url } = await searchParams;
  return <ProviderGate initialUrl={typeof url === "string" ? url : ""} />;
}
