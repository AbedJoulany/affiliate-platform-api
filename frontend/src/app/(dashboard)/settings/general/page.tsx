import { CapabilityView } from "@/features/settings/components/CapabilityView";

export default function GeneralSettingsPage() {
  return <CapabilityView title="الإعدادات العامة" description="تفضيلات واجهة مساحة العمل." details={[["اتجاه الواجهة", "العربية — RTL"], ["السمة", "فاتحة / داكنة / النظام"], ["مساحات العمل", "مؤجلة في الإصدار الحالي"]]} />;
}
