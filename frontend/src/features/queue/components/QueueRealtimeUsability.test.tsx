import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Button } from "@/components/ui/primitives";
import { QueueRealtimeStatusBadge } from "./QueueRealtimeStatusBadge";

afterEach(() => {
  cleanup();
});

describe("F4 — Queue usability while realtime is offline", () => {
  it("does not disable queue actions when realtime is disconnected", () => {
    render(
      <div>
        <QueueRealtimeStatusBadge status="disconnected" />
        <Button type="button">نشر الآن</Button>
        <Button type="button" variant="outline" aria-label="تحديث النتائج">
          تحديث
        </Button>
      </div>,
    );

    expect(
      screen.getByRole("status", {
        name: "البث الحي غير متصل — قائمة النشر تبقى قابلة للاستخدام",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "نشر الآن" })).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "تحديث النتائج" }),
    ).toBeEnabled();
  });
});
