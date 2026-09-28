import type { Metadata } from "next";
import { SupplyScopeApp } from "./supply-scope-app";

export const metadata: Metadata = {
  title: "SupplyScope — Disruption Response",
  description: "A deterministic supply-chain disruption response platform for a synthetic logistics scenario.",
};

export default function Home() {
  return <SupplyScopeApp />;
}
