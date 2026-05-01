// apps/web/components/header.tsx
import Link from "next/link";
import { signOut } from "@/app/actions/auth";
import { Button } from "@/components/ui/button";

export function Header({ email }: { email: string }) {
  return (
    <header className="border-b">
      <div className="mx-auto flex max-w-5xl items-center justify-between p-4">
        <Link href="/" className="text-lg font-semibold">
          Hedgentic AI
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link
            href="/runs/new"
            className="text-muted-foreground hover:text-foreground"
          >
            New run
          </Link>
          <Link
            href="/settings"
            className="text-muted-foreground hover:text-foreground"
          >
            Settings
          </Link>
          <span className="text-muted-foreground">{email}</span>
          <form action={signOut}>
            <Button type="submit" variant="ghost" size="sm">
              Sign out
            </Button>
          </form>
        </nav>
      </div>
    </header>
  );
}
