import { ProductDetailView } from "@/features/products/components/ProductDetailView";

export default async function ProductDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ProductDetailView id={id} />;
}
