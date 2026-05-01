// apps/web/components/masked-key-display.tsx
export function MaskedKeyDisplay({
  provider,
  createdAt,
}: {
  provider: string;
  createdAt: string;
}) {
  const formatted = new Date(createdAt).toLocaleDateString();
  return (
    <code className="font-mono text-sm text-muted-foreground">
      {provider} · added {formatted}
    </code>
  );
}
