import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./shared.css";
import "./match/match.css";
import "./records/records.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
