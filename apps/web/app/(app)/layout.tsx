// apps/web/app/(app)/layout.tsx
import { Header } from "@/components/header";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="min-h-screen bg-background">
      <Header email={user.email ?? ""} />
      <main className="mx-auto max-w-5xl p-6">{children}</main>
    </div>
  );
}
