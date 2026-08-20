import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";

export const metadata: Metadata = {
  title: "GitHub Analytics Dashboard",
  description:
    "Production-grade analytics dashboard for GitHub repositories — powered by AWS Lakehouse architecture with medallion pattern.",
  keywords: ["github", "analytics", "dashboard", "data pipeline", "metrics"],
  authors: [{ name: "GitHub Analytics Data Pipeline" }],
  openGraph: {
    title: "GitHub Analytics Dashboard",
    description: "Visualize commits, PRs, issues and contributor trends across your GitHub repos.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="app-layout">
          <Sidebar />
          <div className="main-content">
            <Header />
            <main className="page-container">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
