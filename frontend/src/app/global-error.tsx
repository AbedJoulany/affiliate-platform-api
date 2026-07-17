"use client";

import { Button } from "@/components/ui/primitives";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="ar" dir="rtl">
      <body className="grid min-h-screen place-items-center bg-background p-4 text-foreground">
        <div className="text-center">
          <h1 className="text-2xl font-semibold">حدث خطأ غير متوقع</h1>
          <p className="mt-2 text-muted-foreground">يمكنك إعادة المحاولة بأمان.</p>
          <Button className="mt-5" onClick={reset}>إعادة المحاولة</Button>
        </div>
      </body>
    </html>
  );
}
