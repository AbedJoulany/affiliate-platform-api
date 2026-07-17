import { AIStudioView } from "@/features/ai/components/AIStudioView";

export default async function AIPage({
  searchParams,
}: {
  searchParams: Promise<{ product?: string; url?: string }>;
}) {
  const { product, url } = await searchParams;
  return <AIStudioView initialProductId={product} initialUrl={url} />;
}
