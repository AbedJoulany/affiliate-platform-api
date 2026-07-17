import type { ReactNode } from "react";
import { AlertTriangle, Inbox } from "lucide-react";
import { Button, Card, Skeleton } from "@/components/ui/primitives";

export function LoadingState({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="جار التحميل">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton className="h-16 w-full" key={index} />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <Card className="flex min-h-56 flex-col items-center justify-center text-center">
      <Inbox className="mb-4 size-9 text-muted-foreground" aria-hidden />
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </Card>
  );
}

export function ErrorState({
  message = "تعذر تحميل البيانات.",
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <Card className="flex min-h-48 flex-col items-center justify-center text-center" role="alert">
      <AlertTriangle className="mb-3 size-8 text-destructive" aria-hidden />
      <p className="font-medium">{message}</p>
      {onRetry && (
        <Button className="mt-4" variant="outline" onClick={onRetry}>
          إعادة المحاولة
        </Button>
      )}
    </Card>
  );
}
