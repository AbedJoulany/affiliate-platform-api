import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { AuthGuard } from "@/features/auth/components/AuthGuard";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  );
}
