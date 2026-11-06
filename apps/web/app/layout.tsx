import type { Metadata } from "next";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import { AppShellWrapper } from "@/components/app-shell-wrapper";

export const metadata: Metadata = {
  title: "FloodAware Pune — Flood-Aware Route & Road Risk Engine",
  description:
    "Real-time flood risk navigation for Pune. Scores roads using terrain, drainage, rainfall, flood history, and citizen reports for safer routing.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
        <meta name="theme-color" content="#0c4a6e" />
      </head>
      <body>
        <AppShellWrapper>{children}</AppShellWrapper>
      </body>
    </html>
  );
}
