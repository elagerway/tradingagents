import Link from "next/link";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NewRunForm } from "@/components/new-run-form";
import { createClient } from "@/lib/supabase/server";

export default async function NewRunPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const params = await searchParams;
  const today = new Date().toISOString().slice(0, 10);

  const supabase = await createClient();
  const { count: keyCount } = await supabase
    .from("api_keys")
    .select("provider", { count: "exact", head: true });

  if (!keyCount) {
    return (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="no-keys-title"
      >
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle id="no-keys-title">Add an LLM key first</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              You need at least one provider key (OpenAI, Anthropic, DeepSeek,
              etc.) before you can start a run. Hedgentic uses your own keys —
              we never store anything plaintext.
            </p>
            <div className="flex gap-2">
              <Link href="/settings" className={buttonVariants()}>
                Go to Settings
              </Link>
              <Link
                href="/"
                className={buttonVariants({ variant: "outline" })}
              >
                Back to runs
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">New run</h1>

      <Card>
        <CardHeader>
          <CardTitle>Configure</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {params.error === "invalid" && (
            <Alert variant="destructive">
              <AlertDescription>
                Check the ticker and date — both are required.
              </AlertDescription>
            </Alert>
          )}
          {params.error === "server" && (
            <Alert variant="destructive">
              <AlertDescription>
                Couldn&apos;t create the run. Try again.
              </AlertDescription>
            </Alert>
          )}

          <NewRunForm today={today} />
        </CardContent>
      </Card>
    </div>
  );
}
