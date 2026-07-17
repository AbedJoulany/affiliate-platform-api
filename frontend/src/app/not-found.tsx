import Link from "next/link";
import { Button, Card } from "@/components/ui/primitives";

export default function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center p-4">
      <Card className="max-w-md text-center">
        <p className="text-sm text-primary">404</p>
        <h1 className="mt-2 text-2xl font-semibold">الصفحة غير موجودة</h1>
        <p className="mt-2 text-sm text-muted-foreground">تحقق من الرابط أو عد إلى لوحة التحكم.</p>
        <Link href="/dashboard"><Button className="mt-5">لوحة التحكم</Button></Link>
      </Card>
    </main>
  );
}
