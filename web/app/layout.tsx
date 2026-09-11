import { headers } from "next/headers";
import { Newsreader, Source_Sans_3 } from "next/font/google";
import { defaultLocale, isLocale } from "@/lib/i18n/config";
import "./globals.css";

const sans = Source_Sans_3({
  subsets: ["latin", "latin-ext"],
  variable: "--font-source",
  weight: ["400", "600"],
});
const serif = Newsreader({
  subsets: ["latin", "latin-ext"],
  variable: "--font-newsreader",
  style: ["normal", "italic"],
  weight: ["400", "500"],
});

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const headerLocale = (await headers()).get("x-locale") ?? defaultLocale;
  const locale = isLocale(headerLocale) ? headerLocale : defaultLocale;

  return (
    <html lang={locale}>
      <body className={`${sans.variable} ${serif.variable} min-h-screen font-sans antialiased`}>
        {children}
      </body>
    </html>
  );
}
