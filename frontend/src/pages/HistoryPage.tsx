import { Alert, Box, Chip, Skeleton, Tab, Table, TableBody, TableCell, TableContainer, TableHead, TablePagination, TableRow, Tabs, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { errorMessage } from "../api/client";
import { historyApi } from "../api/endpoints";
import { describeAction, formatBytes, formatDate, shortHash, titleCase } from "../api/format";
import type { AuditLogItem, DeletionHistoryItem, Page } from "../api/types";
import GlassCard from "../components/GlassCard";
import type { LayoutContext } from "../components/Layout";
import PageHeader from "../components/PageHeader";

function Empty({ text }: { text: string }) {
  return (
    <TableRow>
      <TableCell colSpan={6} sx={{ py: 6, textAlign: "center", border: 0 }}>
        <Typography color="text.secondary">{text}</Typography>
      </TableCell>
    </TableRow>
  );
}

function summarize(log: AuditLogItem): string {
  const d = log.details ?? {};
  const bits: string[] = [];
  if (typeof d.count === "number") bits.push(`${d.count} file${d.count === 1 ? "" : "s"}`);
  if (typeof d.freed_bytes === "number") bits.push(`${formatBytes(d.freed_bytes)} freed`);
  if (typeof d.bytes === "number") bits.push(formatBytes(d.bytes));
  if (typeof d.rejected === "number" && d.rejected > 0) bits.push(`${d.rejected} rejected`);
  if (typeof d.reason === "string" && d.reason) bits.push(`“${d.reason}”`);
  return bits.join(" · ") || "—";
}

export default function HistoryPage() {
  const { refreshKey } = useOutletContext<LayoutContext>();
  const [tab, setTab] = useState<"deletions" | "audit">("deletions");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [deletions, setDeletions] = useState<Page<DeletionHistoryItem> | null>(null);
  const [audit, setAudit] = useState<Page<AuditLogItem> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    const req =
      tab === "deletions"
        ? historyApi.deletions(page + 1, pageSize).then((d) => !cancelled && setDeletions(d))
        : historyApi.audit(page + 1, pageSize).then((d) => !cancelled && setAudit(d));
    req.catch((e) => !cancelled && setError(errorMessage(e)));
    return () => {
      cancelled = true;
    };
  }, [tab, page, pageSize, refreshKey]);

  const current = tab === "deletions" ? deletions : audit;

  return (
    <>
      <PageHeader title="History" subtitle="Every deletion and account action is recorded here." />
      <GlassCard sx={{ p: 0, overflow: "hidden" }}>
        <Tabs
          value={tab}
          onChange={(_, v) => {
            setTab(v);
            setPage(0);
          }}
          textColor="secondary"
          indicatorColor="secondary"
          sx={{ px: 2, borderBottom: "1px solid rgba(255,255,255,.1)" }}
        >
          <Tab value="deletions" label="Deleted files" />
          <Tab value="audit" label="Activity log" />
        </Tabs>
        {error && <Alert severity="error" sx={{ m: 2 }}>{error}</Alert>}
        <TableContainer>
          <Table sx={{ minWidth: 720 }}>
            {tab === "deletions" ? (
              <>
                <TableHead>
                  <TableRow>
                    <TableCell>File</TableCell>
                    <TableCell>Was</TableCell>
                    <TableCell align="right">Size</TableCell>
                    <TableCell>Fingerprint</TableCell>
                    <TableCell>Reason</TableCell>
                    <TableCell>Deleted</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {!deletions && <TableRow><TableCell colSpan={6}><Skeleton height={32} /></TableCell></TableRow>}
                  {deletions?.items.length === 0 && <Empty text="Nothing has been deleted yet." />}
                  {deletions?.items.map((d) => (
                    <TableRow key={d.id} hover>
                      <TableCell sx={{ maxWidth: 280 }}>
                        <Typography noWrap title={d.filename}>{d.filename}</Typography>
                        <Typography variant="caption" color="text.secondary">{titleCase(d.category)}</Typography>
                      </TableCell>
                      <TableCell>
                        {d.was_original ? <Chip size="small" label="Original" color="secondary" variant="outlined" /> : d.was_duplicate ? <Chip size="small" label="Duplicate" color="primary" /> : <Chip size="small" label="Unique" variant="outlined" />}
                      </TableCell>
                      <TableCell align="right">{formatBytes(d.size_bytes)}</TableCell>
                      <TableCell sx={{ fontFamily: "ui-monospace, monospace", fontSize: 13 }}>{shortHash(d.content_hash)}</TableCell>
                      <TableCell>{d.reason ?? "—"}</TableCell>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDate(d.deleted_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </>
            ) : (
              <>
                <TableHead>
                  <TableRow>
                    <TableCell>Action</TableCell>
                    <TableCell>Details</TableCell>
                    <TableCell>IP address</TableCell>
                    <TableCell>When</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {!audit && <TableRow><TableCell colSpan={4}><Skeleton height={32} /></TableCell></TableRow>}
                  {audit?.items.length === 0 && <Empty text="No activity yet." />}
                  {audit?.items.map((a) => (
                    <TableRow key={a.id} hover>
                      <TableCell>
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                          {describeAction(a.action)}
                          {a.action === "auth.login_failed" && <Chip size="small" color="error" variant="outlined" label="Check this" />}
                        </Box>
                      </TableCell>
                      <TableCell>{summarize(a)}</TableCell>
                      <TableCell>{a.ip_address ?? "—"}</TableCell>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDate(a.created_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </>
            )}
          </Table>
        </TableContainer>
        <TablePagination
          component="div"
          count={current?.total ?? 0}
          page={page}
          onPageChange={(_, p) => setPage(p)}
          rowsPerPage={pageSize}
          onRowsPerPageChange={(e) => {
            setPageSize(Number(e.target.value));
            setPage(0);
          }}
          rowsPerPageOptions={[10, 20, 50, 100]}
        />
      </GlassCard>
    </>
  );
}
