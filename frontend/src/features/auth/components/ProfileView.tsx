"use client";

import { useEffect, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { ErrorState, LoadingState } from "@/components/common/states";
import { ToastOverlay } from "@/components/common/ToastOverlay";
import { PageContainer, PageHeader } from "@/components/layout/page";
import { Badge, Button, Card, Input } from "@/components/ui/primitives";
import { getApiErrorMessage } from "@/services/api-client";
import { useCurrentUser, useUpdateProfile } from "../hooks/useAuth";
import { applyApiFieldErrors } from "@/features/settings/lib/mapApiErrors";
import { profileSchema, type ProfileFormValues } from "../lib/schemas";

export function ProfileView() {
  const user = useCurrentUser();
  if (user.isPending) {
    return (
      <PageContainer>
        <LoadingState rows={4} />
      </PageContainer>
    );
  }
  if (user.isError) {
    return (
      <PageContainer>
        <ErrorState onRetry={() => void user.refetch()} />
      </PageContainer>
    );
  }
  return (
    <PageContainer>
      <PageHeader title="الملف الشخصي" description="معلومات الحساب والجلسة الحالية." />
      <ProfileForm
        fullName={user.data.full_name}
        email={user.data.email}
        role={user.data.role}
        isActive={user.data.is_active}
      />
    </PageContainer>
  );
}

function ProfileForm({
  fullName,
  email,
  role,
  isActive,
}: {
  fullName: string;
  email: string;
  role: string;
  isActive: boolean;
}) {
  const update = useUpdateProfile();
  const [toast, setToast] = useState<{ message: string; tone: "success" | "error" } | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<ProfileFormValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { full_name: fullName, email },
  });

  useEffect(() => {
    reset({ full_name: fullName, email });
  }, [fullName, email, reset]);

  return (
    <Card className="max-w-2xl">
      <form
        className="space-y-4"
        onSubmit={handleSubmit((values) => {
          update.mutate(values, {
            onSuccess: () => setToast({ message: "تم حفظ الملف الشخصي.", tone: "success" }),
            onError: (error) => {
              const mapped = applyApiFieldErrors(error, setError, ["full_name", "email"]);
              if (!mapped) {
                setToast({
                  message: getApiErrorMessage(error, "تعذر حفظ الملف الشخصي."),
                  tone: "error",
                });
              }
            },
          });
        })}
      >
        <div>
          <label className="mb-1.5 block text-sm" htmlFor="full_name">
            الاسم الكامل
          </label>
          <Input id="full_name" {...register("full_name")} />
          {errors.full_name && (
            <p className="mt-1 text-sm text-destructive" role="alert">
              {errors.full_name.message}
            </p>
          )}
        </div>
        <div>
          <label className="mb-1.5 block text-sm" htmlFor="email">
            البريد الإلكتروني
          </label>
          <Input dir="ltr" id="email" type="email" {...register("email")} />
          {errors.email && (
            <p className="mt-1 text-sm text-destructive" role="alert">
              {errors.email.message}
            </p>
          )}
        </div>
        <dl className="space-y-3 border-t border-border pt-5 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">الدور</dt>
            <dd>
              <Badge>{role}</Badge>
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">حالة الحساب</dt>
            <dd>
              <Badge tone={isActive ? "success" : "error"}>{isActive ? "نشط" : "غير نشط"}</Badge>
            </dd>
          </div>
        </dl>
        <p className="text-sm text-muted-foreground">الدور وحالة الحساب لا يمكن تعديلهما من هنا.</p>
        <Button loading={update.isPending} type="submit">
          حفظ
        </Button>
      </form>
      <ToastOverlay
        message={toast?.message ?? null}
        tone={toast?.tone}
        onDismiss={() => setToast(null)}
      />
    </Card>
  );
}
