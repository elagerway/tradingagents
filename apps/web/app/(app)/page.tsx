import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { vancouverDateTimeString } from "@/lib/format-date";
import { createClient } from "@/lib/supabase/server";

const STATUS_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  pending: "outline",
  running: "secondary",
  completed: "default",
  failed: "destructive",
};

export default async function RunsListPage() {
  const supabase = await createClient();
  const { data: runs } = await supabase
    .from("runs")
    .select("id, ticker, trade_date, status, created_at, final_decision")
    .order("created_at", { ascending: false })
    .limit(50);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Runs</h1>
        <Link href="/runs/new" className={buttonVariants()}>
          New run
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent runs</CardTitle>
        </CardHeader>
        <CardContent>
          {runs && runs.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Ticker</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Decision</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>
                      <Link
                        href={`/runs/${r.id}`}
                        className="font-medium hover:underline"
                      >
                        {r.ticker}
                      </Link>
                    </TableCell>
                    <TableCell>{r.trade_date}</TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[r.status] ?? "outline"}>
                        {r.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {(r.final_decision as { decision?: string } | null)
                        ?.decision ?? "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {vancouverDateTimeString(r.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-sm text-muted-foreground">
              No runs yet. Click &ldquo;New run&rdquo; to start one.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
