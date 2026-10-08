import DeleteRoundedIcon from "@mui/icons-material/DeleteRounded";
import DownloadRoundedIcon from "@mui/icons-material/DownloadRounded";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import LockOpenRoundedIcon from "@mui/icons-material/LockOpenRounded";
import LockRoundedIcon from "@mui/icons-material/LockRounded";
import ReplayRoundedIcon from "@mui/icons-material/ReplayRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Divider,
  Drawer,
  IconButton,
  InputAdornment,
  MenuItem,
  Skeleton,
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { errorMessage } from "../api/client";
import { filesApi } from "../api/endpoints";
import { formatBytes, formatDate, shortHash, titleCase } from "../api/format";
import type { DeletionResult, DuplicateFilter, FileCategory, FileDetail, FileItem, FileQuery, Page } from "../api/types";
import ConfirmDeleteDialog from "../components/ConfirmDeleteDialog";
import GlassCard from "../components/GlassCard";
import type { LayoutContext } from "../components/Layout";
import PageHeader from "../components/PageHeader";
import { ProtectedChip, StatusChip } from "../components/StatusChips";

const CATEGORIES: FileCategory[] = ["image", "video", "audio", "document", "archive", "code", "other"];
const UNIT: Record<string, number> = { KB: 1024, MB: 1024 ** 2, GB: 1024 ** 3 };
type SortKey = FileQuery["sort_by"];

function Detail({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <Box sx={{ py: 1 }}>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Typography sx={{ wordBreak: "break-all", fontFamily: mono ? "ui-monospace, monospace" : undefined, fontSize: mono ? 13 : undefined }}>{value}</Typography>
    </Box>
  );
}

export default function FilesPage() {
  const { refreshKey, refresh, openUpload } = useOutletContext<LayoutContext>();

  // filters
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [type, setType] = useState<FileCategory | "">("");
  const [duplicates, setDuplicates] = useState<DuplicateFilter>("all");
  const [minSize, setMinSize] = useState("");
  const [maxSize, setMaxSize] = useState("");
  const [unit, setUnit] = useState("MB");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sortBy, setSortBy] = useState<SortKey>("uploaded_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);

  // data
  const [data, setData] = useState<Page<FileItem> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [deleteIds, setDeleteIds] = useState<number[] | null>(null);
  const [detail, setDetail] = useState<FileDetail | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  // debounce the filename search
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(search.trim());
      setPage(0);
    }, 350);
    return () => clearTimeout(t);
  }, [search]);

  const query = useMemo<FileQuery>(() => {
    const factor = UNIT[unit];
    return {
      q: q || undefined,
      file_type: type || undefined,
      duplicates: duplicates === "all" ? undefined : duplicates,
      min_size: minSize !== "" && !Number.isNaN(Number(minSize)) ? Math.round(Number(minSize) * factor) : undefined,
      max_size: maxSize !== "" && !Number.isNaN(Number(maxSize)) ? Math.round(Number(maxSize) * factor) : undefined,
      uploaded_from: from || undefined,
      uploaded_to: to || undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
      page: page + 1,
      page_size: pageSize,
    };
  }, [q, type, duplicates, minSize, maxSize, unit, from, to, sortBy, sortOrder, page, pageSize]);

  const load = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        const res = await filesApi.list(query);
        setData(res);
        setError(null);
        setSelected((prev) => new Set([...prev].filter((id) => res.items.some((f) => f.id === id))));
      } catch (e) {
        setError(errorMessage(e));
      } finally {
        setLoading(false);
      }
    },
    [query],
  );

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  // Poll while any file on screen is still being hashed.
  const hasPending = data?.items.some((f) => f.status === "pending" || f.status === "processing") ?? false;
  useEffect(() => {
    if (!hasPending) return;
    const t = setInterval(() => load(true), 3000);
    return () => clearInterval(t);
  }, [hasPending, load]);

  const resetPage = <T,>(setter: (v: T) => void) => (v: T) => {
    setter(v);
    setPage(0);
  };

  const toggleSort = (key: SortKey) => {
    if (sortBy === key) setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    else {
      setSortBy(key);
      setSortOrder(key === "name" || key === "type" ? "asc" : "desc");
    }
    setPage(0);
  };

  const items = data?.items ?? [];
  const allSelected = items.length > 0 && items.every((f) => selected.has(f.id));
  const toggleAll = () => setSelected(allSelected ? new Set() : new Set(items.map((f) => f.id)));
  const toggleOne = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const download = async (f: FileItem) => {
    setBusyId(f.id);
    try {
      await filesApi.download(f);
    } catch (e) {
      setToast(errorMessage(e, "Download failed."));
    } finally {
      setBusyId(null);
    }
  };

  const toggleProtection = async (f: FileItem) => {
    try {
      await filesApi.setProtection(f.id, !f.is_protected);
      setToast(f.is_protected ? `“${f.original_filename}” is no longer protected.` : `“${f.original_filename}” is protected from deletion.`);
      load(true);
    } catch (e) {
      setToast(errorMessage(e));
    }
  };

  const reprocess = async (f: FileItem) => {
    try {
      await filesApi.reprocess(f.id);
      load(true);
    } catch (e) {
      setToast(errorMessage(e));
    }
  };

  const openDetail = async (f: FileItem) => {
    try {
      setDetail(await filesApi.get(f.id));
    } catch (e) {
      setToast(errorMessage(e));
    }
  };

  const onDeleted = (r: DeletionResult) => {
    setDeleteIds(null);
    setSelected(new Set());
    setToast(`Deleted ${r.deleted_count} file${r.deleted_count === 1 ? "" : "s"} and freed ${formatBytes(r.freed_bytes)}.`);
    load(true);
    refresh();
  };

  const filtersActive = !!(q || type || duplicates !== "all" || minSize || maxSize || from || to);
  const clearFilters = () => {
    setSearch("");
    setQ("");
    setType("");
    setDuplicates("all");
    setMinSize("");
    setMaxSize("");
    setFrom("");
    setTo("");
    setPage(0);
  };

  return (
    <>
      <PageHeader
        title="Files"
        subtitle="Search, filter and manage everything you’ve uploaded."
        actions={
          selected.size > 0 ? (
            <Button variant="contained" startIcon={<DeleteRoundedIcon />} onClick={() => setDeleteIds([...selected])}>
              Delete {selected.size} selected
            </Button>
          ) : undefined
        }
      />

      <GlassCard sx={{ mb: 2, p: 2 }}>
        <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", lg: "2fr 1fr 1.2fr" } }}>
          <TextField
            size="small"
            placeholder="Search by file name"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            inputProps={{ "aria-label": "Search by file name" }}
            InputProps={{ startAdornment: <InputAdornment position="start"><SearchRoundedIcon fontSize="small" /></InputAdornment> }}
          />
          <TextField select size="small" label="File type" value={type} onChange={(e) => resetPage(setType)(e.target.value as FileCategory | "")}>
            <MenuItem value="">All types</MenuItem>
            {CATEGORIES.map((c) => (
              <MenuItem key={c} value={c}>
                {titleCase(c)}
              </MenuItem>
            ))}
          </TextField>
          <TextField select size="small" label="Duplicates" value={duplicates} onChange={(e) => resetPage(setDuplicates)(e.target.value as DuplicateFilter)}>
            <MenuItem value="all">All files</MenuItem>
            <MenuItem value="any">In a duplicate group</MenuItem>
            <MenuItem value="copies">Redundant copies only</MenuItem>
            <MenuItem value="unique">Unique files only</MenuItem>
          </TextField>
        </Box>
        <Box sx={{ display: "grid", gap: 1.5, mt: 1.5, gridTemplateColumns: { xs: "1fr 1fr", lg: "1fr 1fr 90px 1fr 1fr auto" }, alignItems: "center" }}>
          <TextField size="small" type="number" label="Min size" value={minSize} onChange={(e) => resetPage(setMinSize)(e.target.value)} inputProps={{ min: 0 }} />
          <TextField size="small" type="number" label="Max size" value={maxSize} onChange={(e) => resetPage(setMaxSize)(e.target.value)} inputProps={{ min: 0 }} />
          <TextField select size="small" label="Unit" value={unit} onChange={(e) => resetPage(setUnit)(e.target.value)}>
            {Object.keys(UNIT).map((u) => (
              <MenuItem key={u} value={u}>
                {u}
              </MenuItem>
            ))}
          </TextField>
          <TextField size="small" type="date" label="Uploaded from" value={from} onChange={(e) => resetPage(setFrom)(e.target.value)} InputLabelProps={{ shrink: true }} />
          <TextField size="small" type="date" label="Uploaded to" value={to} onChange={(e) => resetPage(setTo)(e.target.value)} InputLabelProps={{ shrink: true }} />
          <Button color="inherit" onClick={clearFilters} disabled={!filtersActive}>
            Clear filters
          </Button>
        </Box>
      </GlassCard>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} action={<Button color="inherit" onClick={() => load()}>Retry</Button>}>
          {error}
        </Alert>
      )}

      <GlassCard sx={{ p: 0, overflow: "hidden" }}>
        <TableContainer>
          <Table size="medium" sx={{ minWidth: 860 }}>
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Checkbox color="secondary" checked={allSelected} indeterminate={selected.size > 0 && !allSelected} onChange={toggleAll} inputProps={{ "aria-label": "Select all files on this page" }} />
                </TableCell>
                <TableCell sortDirection={sortBy === "name" ? sortOrder : false}>
                  <TableSortLabel active={sortBy === "name"} direction={sortBy === "name" ? sortOrder : "asc"} onClick={() => toggleSort("name")}>
                    Name
                  </TableSortLabel>
                </TableCell>
                <TableCell sortDirection={sortBy === "type" ? sortOrder : false}>
                  <TableSortLabel active={sortBy === "type"} direction={sortBy === "type" ? sortOrder : "asc"} onClick={() => toggleSort("type")}>
                    Type
                  </TableSortLabel>
                </TableCell>
                <TableCell align="right" sortDirection={sortBy === "size" ? sortOrder : false}>
                  <TableSortLabel active={sortBy === "size"} direction={sortBy === "size" ? sortOrder : "asc"} onClick={() => toggleSort("size")}>
                    Size
                  </TableSortLabel>
                </TableCell>
                <TableCell sortDirection={sortBy === "uploaded_at" ? sortOrder : false}>
                  <TableSortLabel active={sortBy === "uploaded_at"} direction={sortBy === "uploaded_at" ? sortOrder : "asc"} onClick={() => toggleSort("uploaded_at")}>
                    Uploaded
                  </TableSortLabel>
                </TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading && !data
                ? [...Array(6)].map((_, i) => (
                    <TableRow key={i}>
                      <TableCell colSpan={7}>
                        <Skeleton height={28} />
                      </TableCell>
                    </TableRow>
                  ))
                : items.map((f) => (
                    <TableRow key={f.id} hover selected={selected.has(f.id)}>
                      <TableCell padding="checkbox">
                        <Checkbox color="secondary" checked={selected.has(f.id)} onChange={() => toggleOne(f.id)} inputProps={{ "aria-label": `Select ${f.original_filename}` }} />
                      </TableCell>
                      <TableCell sx={{ maxWidth: 320 }}>
                        <Typography noWrap sx={{ fontWeight: 600 }} title={f.original_filename}>
                          {f.original_filename}
                        </Typography>
                        <Box sx={{ display: "flex", gap: 0.75, mt: 0.5, flexWrap: "wrap" }}>
                          {f.is_duplicate && <Chip size="small" label="Duplicate" color="primary" />}
                          {!f.is_duplicate && f.duplicate_group_id && <Chip size="small" label="Original" color="secondary" variant="outlined" />}
                          {f.is_protected && <ProtectedChip />}
                        </Box>
                      </TableCell>
                      <TableCell>{titleCase(f.category)}</TableCell>
                      <TableCell align="right">{formatBytes(f.size_bytes)}</TableCell>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDate(f.uploaded_at)}</TableCell>
                      <TableCell>
                        <StatusChip file={f} />
                      </TableCell>
                      <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                        {f.status === "failed" && (
                          <Tooltip title="Try hashing again">
                            <IconButton aria-label={`Re-check ${f.original_filename}`} onClick={() => reprocess(f)}>
                              <ReplayRoundedIcon />
                            </IconButton>
                          </Tooltip>
                        )}
                        <Tooltip title="Details">
                          <IconButton aria-label={`Details for ${f.original_filename}`} onClick={() => openDetail(f)}>
                            <InfoOutlinedIcon />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Download">
                          <span>
                            <IconButton aria-label={`Download ${f.original_filename}`} onClick={() => download(f)} disabled={busyId === f.id}>
                              {busyId === f.id ? <CircularProgress size={20} color="secondary" /> : <DownloadRoundedIcon />}
                            </IconButton>
                          </span>
                        </Tooltip>
                        <Tooltip title={f.is_protected ? "Remove protection" : "Protect from deletion"}>
                          <IconButton aria-label={f.is_protected ? "Remove protection" : "Protect from deletion"} onClick={() => toggleProtection(f)}>
                            {f.is_protected ? <LockRoundedIcon color="secondary" /> : <LockOpenRoundedIcon />}
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                          <IconButton aria-label={`Delete ${f.original_filename}`} onClick={() => setDeleteIds([f.id])}>
                            <DeleteRoundedIcon />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
              {!loading && items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} sx={{ py: 8, textAlign: "center", border: 0 }}>
                    <Typography variant="h6">{filtersActive ? "No files match these filters" : "No files yet"}</Typography>
                    <Typography color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
                      {filtersActive ? "Try widening the size range or clearing a filter." : "Upload your first files to start finding duplicates."}
                    </Typography>
                    {filtersActive ? <Button onClick={clearFilters}>Clear filters</Button> : <Button variant="contained" onClick={openUpload}>Upload files</Button>}
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          component="div"
          count={data?.total ?? 0}
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

      <ConfirmDeleteDialog open={deleteIds !== null} fileIds={deleteIds ?? []} onClose={() => setDeleteIds(null)} onDeleted={onDeleted} />

      <Drawer anchor="right" open={!!detail} onClose={() => setDetail(null)} PaperProps={{ className: "glass-strong", sx: { width: { xs: "100%", sm: 420 }, p: 3 } }}>
        {detail && (
          <>
            <Typography variant="h5" sx={{ wordBreak: "break-word" }}>
              {detail.original_filename}
            </Typography>
            <Box sx={{ display: "flex", gap: 1, mt: 1.5, flexWrap: "wrap" }}>
              <StatusChip file={detail} />
              {detail.is_protected && <ProtectedChip />}
              {detail.is_duplicate && <Chip size="small" label="Duplicate" color="primary" />}
            </Box>
            <Divider sx={{ my: 2 }} />
            <Detail label="Size" value={`${formatBytes(detail.size_bytes)} (${detail.size_bytes.toLocaleString()} bytes)`} />
            <Detail label="Type" value={`${titleCase(detail.category)} · ${detail.file_metadata?.detected_mime ?? detail.mime_type}`} />
            <Detail label="Extension" value={detail.extension ? `.${detail.extension}` : "none"} />
            <Detail label="Uploaded" value={formatDate(detail.uploaded_at)} />
            <Detail label="Checked for duplicates" value={formatDate(detail.processed_at)} />
            <Detail label="SHA-256" value={detail.content_hash ?? "Not computed yet"} mono />
            {detail.file_metadata?.signature && <Detail label="Detected format" value={detail.file_metadata.signature} />}
            {detail.status_message && <Alert severity="error" sx={{ mt: 1 }}>{detail.status_message}</Alert>}
            {detail.group && (
              <>
                <Divider sx={{ my: 2 }} />
                <Typography variant="h6">Duplicate group</Typography>
                <Detail label="Copies with identical content" value={detail.group.file_count} />
                <Detail label="Original" value={detail.group.original_filename ?? "—"} />
                <Detail label="Space you could reclaim" value={formatBytes(detail.group.potential_savings)} />
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Content fingerprint {shortHash(detail.content_hash)}
                </Typography>
              </>
            )}
            <Box sx={{ flex: 1 }} />
            <Button sx={{ mt: 3 }} variant="outlined" onClick={() => setDetail(null)}>
              Close
            </Button>
          </>
        )}
      </Drawer>

      <Snackbar open={!!toast} autoHideDuration={5000} onClose={() => setToast(null)} message={toast} anchorOrigin={{ vertical: "bottom", horizontal: "center" }} />
    </>
  );
}
