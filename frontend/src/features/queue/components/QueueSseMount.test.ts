import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const queueRoot = join(process.cwd(), "src/features/queue");

function read(relativePath: string): string {
  return readFileSync(join(queueRoot, relativePath), "utf8");
}

describe("Queue SSE mount topology", () => {
  it("mounts realtime invalidation once from QueueView", () => {
    const view = read("components/QueueView.tsx");
    expect(view).toContain("useQueueRealtimeInvalidation");
    expect(view.match(/useQueueRealtimeInvalidation\(/g)?.length).toBe(1);
    expect(view).toContain("QueueRealtimePollingContext.Provider");
    expect(view).not.toContain("useQueueEventStream(");
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
