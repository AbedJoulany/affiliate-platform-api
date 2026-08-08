import type { Product } from "../types/api";

function escapeCsv(value: string | number | null | undefined): string {
  const text = value == null ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function exportProductsCsv(products: Product[]): void {
  const headers = [
    "id",
    "aliexpress_product_id",
    "title",
    "category",
    "store",
    "price",
    "currency",
    "rating",
    "sales",
    "score",
    "status",
    "product_url",
  ];
  const rows = products.map((product) =>
    [
      product.id,
      product.aliexpress_product_id,
      product.title,
      product.category,
      product.store_name,
      product.price,
      product.currency,
      product.rating,
      product.sales,
      product.score,
      product.status,
      product.product_url,
    ]
      .map(escapeCsv)
      .join(","),
  );
  const blob = new Blob([[headers.join(","), ...rows].join("\n")], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `product-inventory-${Date.now()}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}
