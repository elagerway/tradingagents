// apps/web/app/(app)/settings/page.tsx
import { saveApiKey, deleteApiKey } from "@/app/actions/keys";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MaskedKeyDisplay } from "@/components/masked-key-display";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { createClient } from "@/lib/supabase/server";

const PROVIDERS = [
  "openai",
  "anthropic",
  "google",
  "xai",
  "deepseek",
  "dashscope",
  "zhipu",
  "openrouter",
  "alpha_vantage",
];

export default async function SettingsPage() {
  const supabase = await createClient();
  const { data: keys } = await supabase
    .from("api_keys")
    .select("provider, created_at, last_used_at")
    .order("provider");

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>API keys</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {keys && keys.length > 0 ? (
            <ul className="space-y-2">
              {keys.map((k) => (
                <li
                  key={k.provider}
                  className="flex items-center justify-between border-b pb-2"
                >
                  <MaskedKeyDisplay
                    provider={k.provider}
                    createdAt={k.created_at}
                  />
                  <form action={deleteApiKey as (formData: FormData) => void}>
                    <input type="hidden" name="provider" value={k.provider} />
                    <Button type="submit" variant="ghost" size="sm">
                      Remove
                    </Button>
                  </form>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">No keys saved.</p>
          )}

          <Separator />

          <form action={saveApiKey as (formData: FormData) => void} className="space-y-3">
            <div className="space-y-1">
              <Label>Provider</Label>
              <Select name="provider" defaultValue="openai">
                <SelectTrigger>
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {PROVIDERS.map((p) => (
                    <SelectItem key={p} value={p}>
                      {p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="plaintext">API key</Label>
              <Input
                id="plaintext"
                name="plaintext"
                type="password"
                required
                autoComplete="off"
                placeholder="sk-..."
              />
            </div>
            <Button type="submit">Add key</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
