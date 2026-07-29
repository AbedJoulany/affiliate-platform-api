"use client";

import { Button } from "@/components/ui/primitives";
import type { DiscoveryMode } from "../types/api";

export function DiscoveryEmptyState({
  variant,
  onRun,
  onResetFilters,
  onSwitchMode,
}: {
  variant: "initial" | "no-results";
  onRun: () => void;
  onResetFilters: () => void;
  onSwitchMode: (mode: DiscoveryMode) => void;
}) {
  if (variant === "initial") {
    return (
      <div className="rounded-lg border border-dashed border-border bg-muted/30 px-6 py-10 text-center">
        <h3 className="text-lg font-semibold">ابدأ مساحة اكتشاف المنتجات</h3>
        <p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">
          اضبط المصدر والفلاتر السريعة، ثم شغّل الاكتشاف لمراجعة المرشحين واستيراد الأفضل إلى المسار.
        </p>
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          <Button type="button" onClick={onRun}>
            تشغيل الاكتشاف
          </Button>
          <Button type="button" variant="outline" onClick={() => onSwitchMode("hot")}>
            الأكثر مبيعًا
          </Button>
          <Button type="button" variant="outline" onClick={() => onSwitchMode("deals")}>
            العروض
          </Button>
        </div>
        <ul className="mx-auto mt-6 max-w-md space-y-1 text-start text-sm text-muted-foreground">
          <li>• ابدأ بمصدر «الأكثر مبيعًا» لنتائج سريعة.</li>
          <li>• استخدم شريط الفلاتر لتضييق السعر والتقييم.</li>
          <li>• افتح الفلاتر المتقدمة للكلمات والشحن وChoice.</li>
        </ul>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-dashed border-border bg-muted/30 px-6 py-10 text-center">
      <h3 className="text-lg font-semibold">لا توجد نتائج مطابقة</h3>
      <p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground">
        الفلاتر الحالية ضيّقة جدًا أو لا تتوافق مع مصدر الاكتشاف. جرّب توسيع النطاق ثم أعد التشغيل.
      </p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        <Button type="button" onClick={onRun}>
          إعادة التشغيل
        </Button>
        <Button type="button" variant="outline" onClick={onResetFilters}>
          إعادة تعيين الفلاتر
        </Button>
        <Button type="button" variant="outline" onClick={() => onSwitchMode("trending")}>
          جرّب الرائج
        </Button>
      </div>
      <ul className="mx-auto mt-6 max-w-md space-y-1 text-start text-sm text-muted-foreground">
        <li>• خفّض الحد الأدنى للتقييم أو الطلبات.</li>
        <li>• وسّع نطاق السعر أو امسح كلمات البحث.</li>
        <li>• عطّل «شحن مجاني» أو Choice إن كانا مفعّلين.</li>
      </ul>
    </div>
  );
}
