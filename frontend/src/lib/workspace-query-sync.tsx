"use client";

import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  removeWorkspaceScopedQueries,
  useActiveWorkspaceId,
} from "@/lib/workspace";

/**
 * On workspace A → B, drop tenant query cache so B cannot briefly render A's data.
 * Global product/auth queries are left intact.
 */
export function WorkspaceQuerySync() {
  const queryClient = useQueryClient();
  const workspaceId = useActiveWorkspaceId();
  const previousRef = useRef<string | null>(null);

  useEffect(() => {
    const previous = previousRef.current;
    previousRef.current = workspaceId;
    if (previous !== null && previous !== workspaceId) {
      removeWorkspaceScopedQueries(queryClient);
    }
  }, [workspaceId, queryClient]);

  return null;
}
