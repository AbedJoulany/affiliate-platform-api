import { CapabilityView } from "@/features/settings/components/CapabilityView";

export default function AliExpressSettingsPage() {
  return <CapabilityView title="AliExpress" description="حالة تكامل اكتشاف واستيراد المنتجات." capability="aliexpress" details={[["مصدر المنتجات", "AliExpress API"], ["العملة المستهدفة", "تحددها بيئة الخادم"], ["بلد الشحن", "يحدده إعداد الخادم"]]} />;
}
