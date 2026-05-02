"use client";

import { useRef, useState } from "react";
import { createRun } from "@/app/actions/runs";
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
] as const;

const OPENROUTER_DEFAULTS = {
  deep: "anthropic/claude-sonnet-4.5",
  quick: "openai/gpt-4o-mini",
};

export function NewRunForm({ today }: { today: string }) {
  const [provider, setProvider] = useState<string>("openai");
  const [modalOpen, setModalOpen] = useState(false);
  const [deepModel, setDeepModel] = useState(OPENROUTER_DEFAULTS.deep);
  const [quickModel, setQuickModel] = useState(OPENROUTER_DEFAULTS.quick);

  const formRef = useRef<HTMLFormElement>(null);
  const skipInterceptRef = useRef(false);

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    if (provider === "openrouter" && !skipInterceptRef.current) {
      e.preventDefault();
      setModalOpen(true);
      return;
    }
    skipInterceptRef.current = false;
  }

  function continueOpenrouter() {
    setModalOpen(false);
    skipInterceptRef.current = true;
    formRef.current?.requestSubmit();
  }

  return (
    <>
      <form
        ref={formRef}
        action={createRun}
        onSubmit={handleSubmit}
        className="space-y-4"
      >
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
          <Select
            name="llm_provider"
            value={provider}
            onValueChange={(v) => v && setProvider(v)}
          >
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
        {provider === "openrouter" && (
          <>
            <input type="hidden" name="deep_think_llm" value={deepModel} />
            <input type="hidden" name="quick_think_llm" value={quickModel} />
          </>
        )}
        <Button type="submit">Start run</Button>
      </form>

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="openrouter-models-title"
        >
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle id="openrouter-models-title">
                Pick OpenRouter models
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                OpenRouter routes to many providers. Use{" "}
                <code className="text-foreground">provider/model</code> format
                — e.g., <code>anthropic/claude-sonnet-4.5</code>.
              </p>
              <div className="space-y-1">
                <Label htmlFor="openrouter-deep">
                  Deep-thinking model (Research Manager, Portfolio Manager)
                </Label>
                <Input
                  id="openrouter-deep"
                  value={deepModel}
                  onChange={(e) => setDeepModel(e.target.value)}
                  placeholder="anthropic/claude-sonnet-4.5"
                  required
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="openrouter-quick">
                  Quick-thinking model (analysts, traders)
                </Label>
                <Input
                  id="openrouter-quick"
                  value={quickModel}
                  onChange={(e) => setQuickModel(e.target.value)}
                  placeholder="openai/gpt-4o-mini"
                  required
                />
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={continueOpenrouter}
                  disabled={!deepModel.trim() || !quickModel.trim()}
                >
                  Continue
                </Button>
                <Button variant="outline" onClick={() => setModalOpen(false)}>
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
