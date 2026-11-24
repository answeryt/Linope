import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { Desktop } from "@/desktop/Desktop";
import { presentDesktop } from "@/desktop/present";
import "@/index.css";

function DesktopRoot() {
  useEffect(() => presentDesktop(), []);
  return <Desktop />;
}

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <DesktopRoot />
    </StrictMode>
  );
}
