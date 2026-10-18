import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Academia IA",
  description: "AI tutor that remembers each learner's difficulties and preferences",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
