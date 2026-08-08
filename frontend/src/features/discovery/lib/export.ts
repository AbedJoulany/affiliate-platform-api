import type { DiscoveryProduct } from "../types/api";

function csvEscape(value: string | number | null | undefined): string {
  const text = value == null ? "" : String(value);
  if (/[",\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

/** Client-side export of discovery candidates. No backend dependency. */
export function exportDiscoveryProductsCsv(products: DiscoveryProduct[], filename: string): void {
  const headers = [
    "aliexpress_product_id",
    "title",
    "price",
    "currency",
    "discount",
    "rating",
    "sales",
    "reviews",
    "commission_rate",
    "score",
    "store_name",
    "category",
    "product_url",
    "affiliate_url",
  ];
  const rows = products.map((product) =>
    [
      product.aliexpress_product_id,
      product.title,
      product.price,
      product.currency,
      product.discount,
      product.rating,
      product.sales,
      product.reviews,
      product.commission_rate ?? "",
      product.score,
      product.store_name ?? "",
      product.category ?? "",
      product.product_url,
      product.affiliate_url ?? "",
    ]
      .map(csvEscape)
      .join(","),
  );
  const blob = new Blob([[headers.join(","), ...rows].join("\n")], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
