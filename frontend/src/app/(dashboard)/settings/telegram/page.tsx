import { CapabilityView } from "@/features/settings/components/CapabilityView";

export default function TelegramSettingsPage() {
  return <CapabilityView title="Telegram" description="حالة بوت النشر والتكامل." capability="telegram" details={[["المنصة", "Telegram"], ["صلاحيات القنوات", "تُعرض في صفحة القنوات"], ["رمز البوت", "محفوظ في الخادم"]]} />;
}
