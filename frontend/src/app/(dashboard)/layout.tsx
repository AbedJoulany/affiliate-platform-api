import type { ReactNode } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { AuthGuard } from "@/features/auth/components/AuthGuard";
import { OperationalRealtimeProvider } from "@/features/realtime/OperationalRealtimeProvider";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <OperationalRealtimeProvider>
        <AppShell>{children}</AppShell>
      </OperationalRealtimeProvider>
    </AuthGuard>
  );
}
