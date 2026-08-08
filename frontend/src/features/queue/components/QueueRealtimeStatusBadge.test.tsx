import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { QueueEventStreamStatus } from "../hooks/useQueueEventStream";
import { QueueRealtimeStatusBadge } from "./QueueRealtimeStatusBadge";

afterEach(() => {
  cleanup();
});

describe("QueueRealtimeStatusBadge", () => {
  const cases: Array<{
    status: QueueEventStreamStatus;
    label: string;
    description: string;
  }> = [
    {
      status: "connecting",
      label: "جاري الاتصال…",
      description: "جارٍ الاتصال بالبث الحي",
    },
    {
      status: "connected",
      label: "مباشر",
      description: "البث الحي متصل",
    },
    {
      status: "disconnected",
      label: "غير متصل",
      description: "البث الحي غير متصل — قائمة النشر تبقى قابلة للاستخدام",
    },
    {
      status: "error",
      label: "البث متوقف",
      description: "تعذر استمرار البث الحي — قائمة النشر تبقى قابلة للاستخدام",
    },
  ];

  it.each(cases)(
    "renders $status with accessible label",
    ({ status, label, description }) => {
      render(<QueueRealtimeStatusBadge status={status} />);
      const badge = screen.getByRole("status", { name: description });
      expect(badge).toHaveTextContent(label);
    },
  );

  it("recovers UI from disconnected to connected", () => {
    const { rerender } = render(
      <QueueRealtimeStatusBadge status="disconnected" />,
    );
    expect(
      screen.getByRole("status", {
        name: "البث الحي غير متصل — قائمة النشر تبقى قابلة للاستخدام",
      }),
    ).toBeInTheDocument();

    rerender(<QueueRealtimeStatusBadge status="connecting" />);
    expect(
      screen.getByRole("status", { name: "جارٍ الاتصال بالبث الحي" }),
    ).toBeInTheDocument();

    rerender(<QueueRealtimeStatusBadge status="connected" />);
    expect(
      screen.getByRole("status", { name: "البث الحي متصل" }),
    ).toBeInTheDocument();
  });
});
