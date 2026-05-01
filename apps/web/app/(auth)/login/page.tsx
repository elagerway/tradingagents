// apps/web/app/(auth)/login/page.tsx
import { sendMagicLink } from "@/app/actions/auth";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type SearchParams = {
  reason?: string;
  sent?: string;
  error?: string;
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;

  if (params.reason === "waitlisted") {
    return (
      <main className="flex min-h-screen items-center justify-center p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Beta access pending</CardTitle>
          </CardHeader>
          <CardContent className="text-muted-foreground">
            You&apos;ve signed in, but you&apos;re on the waitlist. We&apos;ll
            email you when access is granted.
          </CardContent>
        </Card>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>tradingagents</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {params.sent === "1" && (
            <Alert>
              <AlertDescription>
                Magic link sent. Check your email.
              </AlertDescription>
            </Alert>
          )}
          {params.error === "invalid_email" && (
            <Alert variant="destructive">
              <AlertDescription>Please enter a valid email.</AlertDescription>
            </Alert>
          )}
          {params.error === "send_failed" && (
            <Alert variant="destructive">
              <AlertDescription>
                Couldn&apos;t send the magic link. Try again in a moment.
              </AlertDescription>
            </Alert>
          )}
          {params.error === "auth_failed" && (
            <Alert variant="destructive">
              <AlertDescription>
                The link expired or is invalid. Request a new one.
              </AlertDescription>
            </Alert>
          )}
          <form action={sendMagicLink} className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                required
                autoComplete="email"
                placeholder="you@example.com"
              />
            </div>
            <Button type="submit" className="w-full">
              Send magic link
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
