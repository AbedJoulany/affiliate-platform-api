import { ContentWorkspaceView } from "@/features/ai/components/ContentWorkspaceView";

export default async function AIPage({
  searchParams,
}: {
  searchParams: Promise<{ product?: string; url?: string }>;
}) {
  const { product, url } = await searchParams;
  return <ContentWorkspaceView initialProductId={product} initialUrl={url} />;
}
