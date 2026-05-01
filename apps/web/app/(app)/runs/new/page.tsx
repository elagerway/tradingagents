import { createRun } from "@/app/actions/runs";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const PROVIDERS = [
  "openai",
  "anthropic",
  "google",
  "xai",
  "deepseek",
  "dashscope",
  "zhipu",
  "openrouter",
];

export default async function NewRunPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const params = await searchParams;
  const today = new Date().toISOString().slice(0, 10);

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

          <form action={createRun} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="ticker">Ticker</Label>
              <Input
                id="ticker"
                name="ticker"
                required
                placeholder="NVDA"
                maxLength={10}
                style={{ textTransform: "uppercase" }}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="trade_date">Trade date</Label>
              <Input
                id="trade_date"
                name="trade_date"
                type="date"
                required
                defaultValue={today}
              />
            </div>
            <div className="space-y-1">
              <Label>LLM provider</Label>
              <Select name="llm_provider" defaultValue="openai">
                <SelectTrigger>
                  <SelectValue />
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
            <Button type="submit">Start run</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
