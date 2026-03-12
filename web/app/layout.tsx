import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Credx Enterprise Dashboard",
  description: "High-fidelity dark-mode credit intelligence dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
