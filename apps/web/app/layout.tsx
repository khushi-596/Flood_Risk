import type { Metadata, Viewport } from "next";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import { AppShellWrapper } from "@/components/app-shell-wrapper";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0c4a6e",
};

export const metadata: Metadata = {
  title: "FloodAware Pune — Flood-Aware Route & Road Risk Engine",
  description:
    "Real-time flood risk navigation for Pune. Scores roads using terrain, drainage, rainfall, flood history, and citizen reports for safer routing.",
  manifest: "/manifest.json",
  icons: {
    icon: "/favicon.svg",
  },
  openGraph: {
    title: "FloodAware Pune",
    description: "Real-time flood risk navigation for Pune",
    type: "website",
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppShellWrapper>{children}</AppShellWrapper>
      </body>
    </html>
  );
}
