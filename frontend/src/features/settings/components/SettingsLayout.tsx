"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { PageContainer, PageHeader } from "@/components/layout/page";

const items = [
  ["عام", "/settings/general"],
  ["AliExpress", "/settings/aliexpress"],
  ["مزوّدو الذكاء", "/settings/ai"],
  ["Telegram", "/settings/telegram"],
  ["الاكتشاف", "/settings/discovery"],
  ["الجدولة", "/settings/scheduling"],
] as const;

export function SettingsLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <PageContainer>
      <PageHeader title="الإعدادات" description="عرض إعدادات وقدرات المنصة المدعومة حاليًا." />
      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <nav className="flex gap-1 overflow-x-auto lg:flex-col" aria-label="أقسام الإعدادات">
          {items.map(([label, href]) => (
            <Link className={cn("whitespace-nowrap rounded-md px-3 py-2 text-sm hover:bg-muted", pathname === href && "bg-muted font-medium text-primary")} href={href} key={href}>{label}</Link>
          ))}
        </nav>
        {children}
      </div>
    </PageContainer>
  );
}
