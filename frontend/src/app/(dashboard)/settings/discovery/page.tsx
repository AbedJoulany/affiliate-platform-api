import { CapabilityView } from "@/features/settings/components/CapabilityView";

export default function DiscoverySettingsPage() {
  return <CapabilityView title="الاكتشاف" description="قدرات اكتشاف المنتجات المتاحة." details={[["المصادر", "عام، رائج، صاعد، عروض، فئات"], ["حفظ النتائج", "اختياري عبر API"], ["التحديث التلقائي", "يديره العامل الخلفي"]]} />;
}
