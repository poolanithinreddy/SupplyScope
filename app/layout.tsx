import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "localhost:3000";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  const origin = `${protocol}://${host}`;
  const description = "Disruption response, grounded in the records that matter.";
  return {
    metadataBase: new URL(origin),
    title: { default: "SupplyScope", template: "%s · SupplyScope" },
    description,
    icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
    openGraph: { title: "SupplyScope", description, type: "website", images: [{ url: `${origin}/og.png`, width: 1733, height: 907, alt: "SupplyScope disruption-to-recovery control tower" }] },
    twitter: { card: "summary_large_image", title: "SupplyScope", description, images: [`${origin}/og.png`] },
  };
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
