import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Desktop } from "@/desktop/Desktop";
import "@/index.css";

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <Desktop />
    </StrictMode>
  );
}
