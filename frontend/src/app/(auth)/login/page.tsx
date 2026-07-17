import { Suspense } from "react";
import { BrainCircuit } from "lucide-react";
import { Card } from "@/components/ui/primitives";
import { LoginForm } from "@/features/auth/components/LoginForm";

export default function LoginPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-background p-4">
      <Card className="w-full max-w-md p-7 sm:p-8">
        <div className="mb-7">
          <div className="mb-5 grid size-11 place-items-center rounded-xl bg-primary text-primary-foreground">
            <BrainCircuit className="size-6" aria-hidden />
          </div>
          <h1 className="text-2xl font-semibold">مرحبًا بعودتك</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            سجّل الدخول إلى مساحة أتمتة التسويق بالعمولة.
          </p>
        </div>
        <Suspense fallback={<div className="h-48 animate-pulse rounded-md bg-muted" />}>
          <LoginForm />
        </Suspense>
      </Card>
    </main>
  );
}
