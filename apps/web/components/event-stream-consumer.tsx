// apps/web/components/event-stream-consumer.tsx
"use client";

import { fetchEventSource } from "@microsoft/fetch-event-source";
import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/browser";
import { env } from "@/lib/env";

export type AgentEvent =
  | { type: "agent_started"; agent: string }
  | { type: "agent_thinking"; agent: string }
  | { type: "agent_completed"; agent: string; summary: string }
  | { type: "agent_error"; agent: string; error: string }
  | { type: "tool_called"; tool: string; args?: string }
  | { type: "tool_result"; result?: string }
  | { type: "run_completed"; decision: string }
  | { type: "run_failed"; error: string };

interface Props {
  runId: string;
  onEvent: (event: AgentEvent) => void;
  onTerminal?: () => void;
}

export function EventStreamConsumer({ runId, onEvent, onTerminal }: Props) {
  const [retryVersion] = useState(0);

  useEffect(() => {
    let stopped = false;
    const ctrl = new AbortController();

    (async () => {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session || stopped) return;

      try {
        await fetchEventSource(
          `${env.RENDER_API_BASE_URL}/runs/${runId}/stream`,
          {
            headers: { Authorization: `Bearer ${session.access_token}` },
            signal: ctrl.signal,
            openWhenHidden: false,

            onopen: async (res) => {
              if (res.ok) return;
              if (res.status === 401 || res.status === 403) {
                throw new Error(`auth ${res.status}`);
              }
              throw new Error(`server ${res.status}`);
            },
            onmessage: (msg) => {
              if (!msg.data) return;
              try {
                const data = JSON.parse(msg.data) as AgentEvent;
                onEvent(data);
                if (
                  data.type === "run_completed" ||
                  data.type === "run_failed"
                ) {
                  ctrl.abort();
                  onTerminal?.();
                }
              } catch {
                // non-JSON event — ignore
              }
            },
            onerror: (err) => {
              if (ctrl.signal.aborted) throw err; // stop retry loop
              return;
            },
            onclose: () => {
              // Library default behavior: retry. Caller can force a fresh
              // start via key prop / unmount-remount cycle.
            },
          }
        );
      } catch {
        // intentional abort or fatal error — caller decides what to do next
      }
    })();

    return () => {
      stopped = true;
      ctrl.abort();
    };
  }, [runId, retryVersion, onEvent, onTerminal]);

  // Pure logic component — renders nothing.
  return null;
}
