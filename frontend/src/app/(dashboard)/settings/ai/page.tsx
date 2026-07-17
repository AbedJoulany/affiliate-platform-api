import { CapabilityView } from "@/features/settings/components/CapabilityView";

export default function AISettingsPage() {
  return <CapabilityView title="مزوّدو الذكاء الاصطناعي" description="حالة مزوّدي إنشاء المحتوى." capability="ai" details={[["المزوّدون المدعومون", "OpenAI، Gemini"], ["المزوّد الافتراضي", "يحدده الخادم"], ["مفاتيح API", "محفوظة في الخادم"]]} />;
}
