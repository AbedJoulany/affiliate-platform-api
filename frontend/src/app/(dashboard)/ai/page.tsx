import { AIStudioView } from "@/features/ai/components/AIStudioView";

export default async function AIPage({
  searchParams,
}: {
  searchParams: Promise<{ product?: string }>;
}) {
  const { product } = await searchParams;
  return <AIStudioView initialProductId={product} />;
}
