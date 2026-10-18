"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api/health";

import { type SystemStatusState, SystemStatusView } from "../components/SystemStatusView";

export function SystemStatusContainer() {
  const [state, setState] = useState<SystemStatusState>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    getHealth()
      .then((report) => active && setState({ kind: "loaded", report }))
      .catch(() => active && setState({ kind: "unreachable" }));
    return () => {
      active = false;
    };
  }, []);

  return <SystemStatusView state={state} />;
}
