"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import {
  Bot,
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  Compass,
  LayoutDashboard,
  ChartLine,
  LogOut,
  Menu,
  Moon,
  Package,
  Radio,
  Settings,
  Sun,
  User,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/primitives";
import { useCurrentUser, useLogout } from "@/features/auth/hooks/useAuth";

const navigation = [
  { label: "لوحة التحكم", href: "/dashboard", icon: LayoutDashboard },
  { label: "المنتجات", href: "/products", icon: Package },
  { label: "الاكتشاف", href: "/discovery", icon: Compass },
  { label: "محتوى التسويق", href: "/ai", icon: BrainCircuit },
  { label: "قائمة النشر", href: "/queue", icon: Radio },
  { label: "التحليلات", href: "/analytics", icon: ChartLine },
  { label: "القنوات", href: "/channels", icon: Bot },
  { label: "الإعدادات", href: "/settings", icon: Settings },
] as const;

function Navigation({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="space-y-1" aria-label="التنقل الرئيسي">
      {navigation.map(({ label, href, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            className={cn(
              "flex h-10 items-center gap-3 rounded-md px-3 text-sm transition hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
              active && "bg-muted font-medium text-primary",
              collapsed && "justify-center px-0",
            )}
            href={href}
            key={href}
            onClick={onNavigate}
            title={collapsed ? label : undefined}
          >
            <Icon className="size-4 shrink-0" aria-hidden />
            {!collapsed && <span>{label}</span>}
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const { resolvedTheme, setTheme } = useTheme();
  const { data: user } = useCurrentUser();
  const logout = useLogout();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <aside
        className={cn(
          "fixed inset-y-0 right-0 z-40 hidden border-l border-border bg-surface p-3 transition-[width] lg:block",
          collapsed ? "w-20" : "w-64",
        )}
      >
        <div className="mb-7 flex h-10 items-center gap-3 px-2">
          <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground">
            <BrainCircuit className="size-5" aria-hidden />
          </div>
          {!collapsed && <span className="font-semibold">منصة الأفلييت</span>}
        </div>
        <Navigation collapsed={collapsed} />
        <Button
          aria-label={collapsed ? "توسيع الشريط الجانبي" : "طي الشريط الجانبي"}
          className="absolute bottom-4 left-4 right-4 px-2"
          onClick={() => setCollapsed((value) => !value)}
          variant="ghost"
        >
          {collapsed ? <ChevronLeft className="size-4" /> : <><ChevronRight className="size-4" /> طي القائمة</>}
        </Button>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} aria-label="إغلاق القائمة" />
          <aside className="absolute inset-y-0 right-0 w-72 bg-surface p-4 shadow-xl">
            <Button className="mb-5 px-2" variant="ghost" onClick={() => setMobileOpen(false)} aria-label="إغلاق">
              <X className="size-5" />
            </Button>
            <Navigation collapsed={false} onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <div className={cn("transition-[padding]", collapsed ? "lg:pr-20" : "lg:pr-64")}>
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/90 px-4 backdrop-blur sm:px-6">
          <Button className="px-2 lg:hidden" variant="ghost" onClick={() => setMobileOpen(true)} aria-label="فتح القائمة">
            <Menu className="size-5" />
          </Button>
          <div className="hidden text-sm text-muted-foreground sm:block">مساحة أتمتة التسويق بالعمولة</div>
          <div className="relative flex items-center gap-1">
            <Button
              className="px-2"
              variant="ghost"
              onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
              aria-label="تبديل السمة"
            >
              {resolvedTheme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </Button>
            <Button variant="ghost" onClick={() => setUserOpen((value) => !value)} aria-expanded={userOpen}>
              <span className="grid size-7 place-items-center rounded-full bg-primary text-xs text-primary-foreground">
                {user?.full_name?.slice(0, 1) ?? "م"}
              </span>
              <span className="hidden sm:inline">{user?.full_name ?? "الحساب"}</span>
            </Button>
            {userOpen && (
              <div className="absolute left-0 top-12 w-52 rounded-lg border border-border bg-surface p-1 shadow-md">
                <Link className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted" href="/profile" onClick={() => setUserOpen(false)}>
                  <User className="size-4" /> الملف الشخصي
                </Link>
                <button className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-muted" onClick={logout}>
                  <LogOut className="size-4" /> تسجيل الخروج
                </button>
              </div>
            )}
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}
