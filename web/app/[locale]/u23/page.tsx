import { redirect } from "next/navigation";
import { isLocale } from "@/lib/i18n/config";
import { localePath } from "@/lib/i18n";

export default async function Under23Redirect({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isLocale(locale)) redirect("/es/ranking?pos=U23");
  redirect(localePath(locale, "/ranking?pos=U23"));
}
