"use client";

import { ErrorState, LoadingState } from "@/components/common/states";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Badge, Card } from "@/components/ui/primitives";
import { useCurrentUser } from "../hooks/useAuth";

export function ProfileView() {
  const user = useCurrentUser();
  if (user.isPending) return <PageContainer><LoadingState rows={4} /></PageContainer>;
  if (user.isError) return <PageContainer><ErrorState onRetry={() => void user.refetch()} /></PageContainer>;
  return (
    <PageContainer>
      <PageHeader title="الملف الشخصي" description="معلومات الحساب والجلسة الحالية." />
      <Card className="max-w-2xl">
        <div className="mb-6 flex items-center gap-4">
          <div className="grid size-14 place-items-center rounded-full bg-primary text-xl text-primary-foreground">{user.data.full_name.slice(0, 1)}</div>
          <div><h2 className="font-semibold">{user.data.full_name}</h2><p className="text-sm text-muted-foreground">{user.data.email}</p></div>
        </div>
        <dl className="space-y-3 border-t border-border pt-5 text-sm">
          <div className="flex justify-between"><dt className="text-muted-foreground">الدور</dt><dd><Badge>{user.data.role}</Badge></dd></div>
          <div className="flex justify-between"><dt className="text-muted-foreground">حالة الحساب</dt><dd><Badge tone={user.data.is_active ? "success" : "error"}>{user.data.is_active ? "نشط" : "غير نشط"}</Badge></dd></div>
          <div className="flex justify-between"><dt className="text-muted-foreground">البريد</dt><dd dir="ltr">{user.data.email}</dd></div>
        </dl>
        <p className="mt-6 rounded-md bg-muted p-3 text-sm text-muted-foreground">تعديل الملف الشخصي وإعدادات الأمان غير مدعومين حاليًا من واجهة API، لذلك تعرض الصفحة المعلومات فقط.</p>
      </Card>
    </PageContainer>
  );
}
