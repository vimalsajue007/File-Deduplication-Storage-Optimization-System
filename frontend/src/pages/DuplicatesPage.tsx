import AutorenewRoundedIcon from "@mui/icons-material/AutorenewRounded";
import DeleteSweepRoundedIcon from "@mui/icons-material/DeleteSweepRounded";
import DeleteRoundedIcon from "@mui/icons-material/DeleteRounded";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  MenuItem,
  Pagination,
  Skeleton,
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useState } from "react";
import { Link as RouterLink, useOutletContext } from "react-router-dom";
import { errorMessage } from "../api/client";
import { duplicatesApi, filesApi } from "../api/endpoints";
import { formatBytes, formatDate, shortHash } from "../api/format";
import type { DeletionResult, DuplicateGroup, FileItem, Page } from "../api/types";
import ConfirmDeleteDialog from "../components/ConfirmDeleteDialog";
import GlassCard from "../components/GlassCard";
import type { LayoutContext } from "../components/Layout";
import PageHeader from "../components/PageHeader";
import { ProtectedChip } from "../components/StatusChips";

const PAGE_SIZE = 10;

function Metric({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <Box sx={{ minWidth: 96 }}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 700 }} color={accent ? "secondary" : "text.primary"}>
        {value}
      </Typography>
    </Box>
  );
}

export default function DuplicatesPage() {
  const { refreshKey, refresh } = useOutletContext<LayoutContext>();
  const [data, setData] = useState<Page<DuplicateGroup> | null>(null);
  const [sortBy, setSortBy] = useState("savings");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleteIds, setDeleteIds] = useState<number[] | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | false>(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await duplicatesApi.groups({ sort_by: sortBy, page, page_size: PAGE_SIZE }));
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [sortBy, page]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const download = async (f: FileItem) => {
    try {
      await filesApi.download(f);
    } catch (e) {
      setToast(errorMessage(e, "Download failed."));
    }
  };

  const rescan = async () => {
    try {
      const r = await duplicatesApi.rescan();
      setToast(r.queued ? "Re-scan started. Results update in a moment." : "The background worker is unavailable right now.");
      setTimeout(() => load(), 2500);
    } catch (e) {
      setToast(errorMessage(e));
    }
  };

  const onDeleted = (r: DeletionResult) => {
    setDeleteIds(null);
    setToast(`Freed ${formatBytes(r.freed_bytes)} by deleting ${r.deleted_count} file${r.deleted_count === 1 ? "" : "s"}.`);
    load();
    refresh();
  };

  const totalSavings = data?.items.reduce((s, g) => s + g.potential_savings, 0) ?? 0;

  return (
    <>
      <PageHeader
        title="Duplicates"
        subtitle="Files grouped by identical content. The earliest upload is kept as the original."
        actions={
          <>
            <TextField select size="small" label="Sort groups by" value={sortBy} onChange={(e) => { setSortBy(e.target.value); setPage(1); }} sx={{ minWidth: 190 }}>
              <MenuItem value="savings">Most space to reclaim</MenuItem>
              <MenuItem value="size">Largest file</MenuItem>
              <MenuItem value="count">Most copies</MenuItem>
              <MenuItem value="recent">Recently changed</MenuItem>
            </TextField>
            <Button variant="outlined" startIcon={<AutorenewRoundedIcon />} onClick={rescan}>
              Re-scan
            </Button>
          </>
        }
      />

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {loading && !data && [...Array(3)].map((_, i) => <Skeleton key={i} variant="rounded" height={92} sx={{ mb: 2, borderRadius: 5 }} />)}

      {data && data.total === 0 && (
        <GlassCard sx={{ textAlign: "center", py: 8 }}>
          <Typography variant="h5">No duplicates found</Typography>
          <Typography color="text.secondary" sx={{ mt: 1, mb: 3 }}>
            Every file you’ve uploaded has unique content. New uploads are checked automatically.
          </Typography>
          <Button component={RouterLink} to="/files" variant="outlined">
            Go to files
          </Button>
        </GlassCard>
      )}

      {data && data.total > 0 && (
        <Typography color="text.secondary" sx={{ mb: 1.5 }}>
          {data.total} group{data.total === 1 ? "" : "s"}. On this page you can reclaim {formatBytes(totalSavings)}.
        </Typography>
      )}

      {data?.items.map((g) => {
        const removable = g.duplicates.filter((d) => !d.is_protected).map((d) => d.id);
        return (
          <Accordion
            key={g.id}
            expanded={expanded === g.id}
            onChange={(_, open) => setExpanded(open ? g.id : false)}
            disableGutters
            className="glass"
            sx={{ mb: 2, "&:before": { display: "none" }, background: undefined, color: "inherit" }}
            slotProps={{ transition: { unmountOnExit: true } }}
          >
            <AccordionSummary expandIcon={<ExpandMoreRoundedIcon />} sx={{ px: 3, py: 0.5 }}>
              <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: { xs: 2, md: 4 }, width: "100%", pr: 2 }}>
                <Box sx={{ flex: "1 1 220px", minWidth: 0 }}>
                  <Typography noWrap sx={{ fontWeight: 700 }} title={g.original?.original_filename}>
                    {g.original?.original_filename ?? "Original removed"}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {g.file_count} identical copies · fingerprint {shortHash(g.content_hash)}
                  </Typography>
                </Box>
                <Metric label="File size" value={formatBytes(g.file_size)} />
                <Metric label="Storage used" value={formatBytes(g.total_storage)} />
                <Metric label="You can reclaim" value={formatBytes(g.potential_savings)} accent />
              </Box>
            </AccordionSummary>
            <AccordionDetails sx={{ px: 3, pb: 3 }}>
              <TableContainer>
                <Table size="small" sx={{ minWidth: 640 }}>
                  <TableHead>
                    <TableRow>
                      <TableCell>File</TableCell>
                      <TableCell>Role</TableCell>
                      <TableCell align="right">Size</TableCell>
                      <TableCell>Uploaded</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {[...(g.original ? [g.original] : []), ...g.duplicates].map((f) => (
                      <TableRow key={f.id}>
                        <TableCell sx={{ maxWidth: 300 }}>
                          <Typography noWrap title={f.original_filename}>
                            {f.original_filename}
                          </Typography>
                          {f.is_protected && <ProtectedChip />}
                        </TableCell>
                        <TableCell>{f.id === g.original?.id ? <Chip size="small" label="Original" color="secondary" variant="outlined" /> : <Chip size="small" label="Duplicate" color="primary" />}</TableCell>
                        <TableCell align="right">{formatBytes(f.size_bytes)}</TableCell>
                        <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDate(f.uploaded_at)}</TableCell>
                        <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                          <Tooltip title="Download">
                            <IconButton aria-label={`Download ${f.original_filename}`} onClick={() => download(f)}>
                              <DownloadRoundedIcon />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title={f.is_protected ? "Protected files can’t be deleted" : "Delete this copy"}>
                            <span>
                              <IconButton aria-label={`Delete ${f.original_filename}`} disabled={f.is_protected} onClick={() => setDeleteIds([f.id])}>
                                <DeleteRoundedIcon />
                              </IconButton>
                            </span>
                          </Tooltip>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              <Box sx={{ display: "flex", justifyContent: "flex-end", mt: 2 }}>
                <Button variant="contained" startIcon={<DeleteSweepRoundedIcon />} disabled={removable.length === 0} onClick={() => setDeleteIds(removable)}>
                  Delete {removable.length} duplicate{removable.length === 1 ? "" : "s"} · {formatBytes(removable.length * g.file_size)}
                </Button>
              </Box>
            </AccordionDetails>
          </Accordion>
        );
      })}

      {data && data.pages > 1 && (
        <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
          <Pagination count={data.pages} page={page} onChange={(_, p) => setPage(p)} color="primary" shape="rounded" />
        </Box>
      )}

      <ConfirmDeleteDialog open={deleteIds !== null} fileIds={deleteIds ?? []} onClose={() => setDeleteIds(null)} onDeleted={onDeleted} />
      <Snackbar open={!!toast} autoHideDuration={5000} onClose={() => setToast(null)} message={toast} anchorOrigin={{ vertical: "bottom", horizontal: "center" }} />
    </>
  );
}
