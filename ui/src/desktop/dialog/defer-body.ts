import { useEffect, useState } from "react";

/** True one frame after the shell opens, so the reveal can start before the heavy tree mounts. */
function useDeferredBody(open: boolean): boolean {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!open) {
      setReady(false);
      return;
    }
    const frame = requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(frame);
  }, [open]);
  return ready;
}

export { useDeferredBody };
