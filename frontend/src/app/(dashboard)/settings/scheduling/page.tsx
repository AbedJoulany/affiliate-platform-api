import { CapabilityView } from "@/features/settings/components/CapabilityView";

export default function SchedulingSettingsPage() {
  return <CapabilityView title="الجدولة" description="قدرات جدولة ونشر المحتوى." details={[["الحالات", "مسودة، انتظار، مجدول، منشور"], ["منطقة الوقت", "تُرسل كوقت ISO للخادم"], ["وتيرة العامل", "تحددها بيئة الخادم"]]} />;
}
