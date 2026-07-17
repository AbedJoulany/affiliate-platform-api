"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { LoadingState } from "@/components/common/states";
import { useCurrentUser } from "../hooks/useAuth";
import { session } from "@/services/session";

export function AuthGuard({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [hasToken, setHasToken] = useState<boolean | null>(null);
  const user = useCurrentUser(hasToken === true);

  useEffect(() => {
    setHasToken(Boolean(session.getAccessToken()));
  }, []);

  useEffect(() => {
    if (hasToken === false || user.isError) router.replace("/login");
  }, [hasToken, router, user.isError]);

  if (hasToken !== true || user.isPending || user.isError) {
    return <div className="p-8"><LoadingState rows={5} /></div>;
  }
  return children;
}
