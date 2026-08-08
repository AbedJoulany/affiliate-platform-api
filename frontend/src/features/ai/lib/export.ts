export function downloadContent(
  content: string,
  format: "txt" | "md" | "html",
  filenameBase = "marketing-content",
): void {
  const body =
    format === "html"
      ? `<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><title>${filenameBase}</title><body><pre style="white-space:pre-wrap;font-family:sans-serif">${escapeHtml(content)}</pre></body></html>`
      : content;
  const mime =
    format === "html" ? "text/html;charset=utf-8" : "text/plain;charset=utf-8";
  const blob = new Blob([body], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${filenameBase}.${format}`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
