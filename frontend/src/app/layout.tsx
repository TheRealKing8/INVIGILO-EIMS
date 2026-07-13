import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AiAssistantFloating } from "@/components/ai-assistant-floating";
import { AuthProvider } from "@/lib/auth";
import { ThemeProvider, ThemeScript } from "@/lib/theme";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "INVIGILO | Smart Examination Invigilation System",
  description:
    "A modern platform for scheduling, assigning, and monitoring examination invigilation operations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      data-scroll-behavior="smooth"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        <ThemeScript />
        <AuthProvider>
          <ThemeProvider>
            <div className="relative min-h-full flex-1">
              {children}
              <AiAssistantFloating />
            </div>
          </ThemeProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
