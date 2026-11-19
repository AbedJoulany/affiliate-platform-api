import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const queueRoot = join(process.cwd(), "src/features/queue");

function read(relativePath: string): string {
  return readFileSync(join(queueRoot, relativePath), "utf8");
}

describe("Queue SSE mount topology", () => {
  it("consumes the shared operational realtime status from QueueView", () => {
    const view = read("components/QueueView.tsx");
    expect(view).toContain("useQueueRealtimeStatus");
    expect(view).not.toContain("useQueueRealtimeInvalidation");
    expect(view).not.toContain("QueueRealtimePollingContext.Provider");
    expect(view).not.toContain("useQueueEventStream(");
  });

  it("owns the shared stream from the operational layout provider", () => {
    const provider = read("../realtime/OperationalRealtimeProvider.tsx");
    expect(provider).toContain("useQueueRealtimeInvalidation");
    expect(provider.match(/useQueueRealtimeInvalidation\(/g)?.length).toBe(1);
    expect(provider).toContain("QueueRealtimePollingContext.Provider");
    expect(provider).toContain('"/dashboard"');
    expect(provider).toContain('"/queue"');
  });

  it("does not open SSE connections from child workspace components", () => {
    const children = [
      "components/QueueTable.tsx",
      "components/QueueOperationalStats.tsx",
      "components/QueueDetailsDrawer.tsx",
      "components/QueueToolbar.tsx",
      "components/QueueSelectionBar.tsx",
      "components/QueueRealtimeStatusBadge.tsx",
    ];

    for (const child of children) {
      const source = read(child);
      expect(source).not.toMatch(/useQueueEventStream\s*\(/);
      expect(source).not.toMatch(/useQueueRealtimeInvalidation\s*\(/);
      expect(source).not.toContain("createQueueEventStream");
    }
  });
});
