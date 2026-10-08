import CloudUploadRoundedIcon from "@mui/icons-material/CloudUploadRounded";
import { Alert, Box, Button, Chip, CircularProgress, List, ListItem, ListItemText, Skeleton, Typography } from "@mui/material";
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  Tooltip,
  type ChartOptions,
} from "chart.js";
import { useEffect, useState } from "react";
import { Bar, Doughnut } from "react-chartjs-2";
import { Link as RouterLink, useOutletContext } from "react-router-dom";
import { errorMessage } from "../api/client";
import { analyticsApi } from "../api/endpoints";
import { formatBytes, formatDate, titleCase } from "../api/format";
import type { Analytics, FileItem } from "../api/types";
import GlassCard from "../components/GlassCard";
import PageHeader from "../components/PageHeader";
import type { LayoutContext } from "../components/Layout";

ChartJS.register(ArcElement, BarElement, CategoryScale, LinearScale, Tooltip, Legend);
ChartJS.defaults.color = "#c9a9ad";
ChartJS.defaults.font.family = "Manrope, system-ui, sans-serif";

const CATEGORY_COLORS = ["#c9506b", "#e9cfae", "#8c1f42", "#e08aa0", "#a07a4f", "#5a1226", "#d8b4a0"];

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <GlassCard sx={{ p: 2.5 }}>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="h4" className="display-font" sx={{ mt: 0.5, fontVariantNumeric: "lining-nums" }}>
        {value}
      </Typography>
      {hint && (
        <Typography variant="caption" color="text.secondary">
          {hint}
        </Typography>
      )}
    </GlassCard>
  );
}

function FileList({ title, files, metric }: { title: string; files: FileItem[]; metric: (f: FileItem) => string }) {
  return (
    <GlassCard>
      <Typography variant="h6" sx={{ mb: 1 }}>
        {title}
      </Typography>
      {files.length === 0 ? (
        <Typography color="text.secondary">Nothing here yet.</Typography>
      ) : (
        <List disablePadding>
          {files.map((f) => (
            <ListItem key={f.id} disableGutters divider sx={{ gap: 1 }}>
              <ListItemText
                primary={f.original_filename}
                secondary={titleCase(f.category)}
                primaryTypographyProps={{ noWrap: true }}
                sx={{ minWidth: 0 }}
              />
              {f.is_duplicate && <Chip size="small" label="Duplicate" color="primary" variant="outlined" />}
              <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
                {metric(f)}
              </Typography>
            </ListItem>
          ))}
        </List>
      )}
    </GlassCard>
  );
}

export default function Dashboard() {
  const { refreshKey, openUpload } = useOutletContext<LayoutContext>();
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      analyticsApi
        .summary()
        .then((d) => !cancelled && (setData(d), setError(null)))
        .catch((e) => !cancelled && setError(errorMessage(e)));
    load();
    // While files are still being hashed, keep numbers fresh.
    const timer = setInterval(() => data?.pending_files && load(), 4000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey, data?.pending_files]);

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!data)
    return (
      <>
        <PageHeader title="Dashboard" />
        <Skeleton variant="rounded" height={190} sx={{ borderRadius: 5, mb: 2 }} />
        <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr 1fr", lg: "repeat(4,1fr)" } }}>
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} variant="rounded" height={104} sx={{ borderRadius: 5 }} />
          ))}
        </Box>
      </>
    );

  if (data.total_files === 0)
    return (
      <>
        <PageHeader title="Dashboard" />
        <GlassCard sx={{ textAlign: "center", py: 8 }}>
          <Typography variant="h5">No files yet</Typography>
          <Typography color="text.secondary" sx={{ mt: 1, mb: 3 }}>
            Upload a few files and Dedupe will tell you which ones are the same inside.
          </Typography>
          <Button variant="contained" startIcon={<CloudUploadRoundedIcon />} onClick={openUpload}>
            Upload files
          </Button>
        </GlassCard>
      </>
    );

  const uniqueStorage = Math.max(data.total_storage - data.duplicate_storage, 0);
  const keptInGroups = Math.max(data.duplicate_storage - data.potential_savings, 0);
  const pct = (n: number) => (data.total_storage ? (n / data.total_storage) * 100 : 0);

  const chartBase: ChartOptions<"bar"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { backgroundColor: "rgba(30,6,15,.95)", borderColor: "rgba(255,255,255,.15)", borderWidth: 1 } },
    scales: {
      x: { grid: { display: false }, ticks: { maxRotation: 0 } },
      y: { grid: { color: "rgba(255,255,255,.07)" }, beginAtZero: true, ticks: { precision: 0 } },
    },
  };

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle={data.pending_files > 0 ? `${data.pending_files} file(s) are still being checked for duplicates.` : undefined}
        actions={data.pending_files > 0 ? <CircularProgress size={22} color="secondary" /> : undefined}
      />

      {/* Hero: the reclaimable storage, as a proportion of everything you store */}
      <GlassCard sx={{ p: { xs: 3, md: 4 }, mb: 2 }}>
        <Box sx={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 3, alignItems: "flex-end" }}>
          <Box>
            <Typography color="text.secondary">You can get back</Typography>
            <Typography className="display-font" sx={{ fontSize: { xs: 48, md: 68 }, fontWeight: 600, lineHeight: 1.05, letterSpacing: "-0.02em" }}>
              {formatBytes(data.potential_savings)}
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 1 }}>
              {data.potential_savings > 0
                ? `${data.savings_percent}% of your ${formatBytes(data.total_storage)}, by removing ${data.duplicate_files} redundant cop${data.duplicate_files === 1 ? "y" : "ies"}.`
                : "No redundant copies found."}
            </Typography>
          </Box>
          {data.potential_savings > 0 && (
            <Button component={RouterLink} to="/duplicates" variant="contained" size="large">
              Review duplicates
            </Button>
          )}
        </Box>
        <Box sx={{ mt: 3 }}>
          <Box className="meter-sheen" sx={{ display: "flex", height: 14, borderRadius: 8, overflow: "hidden", background: "rgba(255,255,255,.08)" }} role="img" aria-label="Storage split between unique files, kept originals and redundant copies">
            <Box sx={{ width: `${pct(uniqueStorage)}%`, background: "rgba(247,235,232,.35)" }} />
            <Box sx={{ width: `${pct(keptInGroups)}%`, background: "#8c1f42" }} />
            <Box sx={{ width: `${pct(data.potential_savings)}%`, background: "linear-gradient(90deg,#c9506b,#e9cfae)" }} />
          </Box>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 3, mt: 1.5 }}>
            {[
              ["rgba(247,235,232,.35)", "Unique files", uniqueStorage],
              ["#8c1f42", "Originals with copies", keptInGroups],
              ["#e9cfae", "Redundant copies", data.potential_savings],
            ].map(([color, label, bytes]) => (
              <Box key={label as string} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Box sx={{ width: 10, height: 10, borderRadius: "50%", background: color as string }} />
                <Typography variant="body2" color="text.secondary">
                  {label as string}: {formatBytes(bytes as number)}
                </Typography>
              </Box>
            ))}
          </Box>
        </Box>
      </GlassCard>

      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr 1fr", lg: "repeat(5, 1fr)" }, mb: 2 }}>
        <Stat label="Total files" value={data.total_files.toLocaleString()} />
        <Stat label="Total storage" value={formatBytes(data.total_storage)} />
        <Stat label="Duplicate files" value={data.duplicate_files.toLocaleString()} hint={`in ${data.duplicate_groups} group${data.duplicate_groups === 1 ? "" : "s"}`} />
        <Stat label="Duplicate storage" value={formatBytes(data.duplicate_storage)} hint="originals + copies" />
        <Stat label="Potential savings" value={formatBytes(data.potential_savings)} hint="copies only" />
      </Box>

      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", lg: "1fr 1.4fr" }, mb: 2 }}>
        <GlassCard>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Storage by file type
          </Typography>
          <Box sx={{ height: 260 }}>
            <Doughnut
              data={{
                labels: data.storage_by_category.map((c) => titleCase(c.category)),
                datasets: [{ data: data.storage_by_category.map((c) => c.bytes), backgroundColor: CATEGORY_COLORS, borderColor: "rgba(20,5,11,.9)", borderWidth: 3 }],
              }}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                cutout: "64%",
                plugins: {
                  legend: { position: "right", labels: { boxWidth: 10, usePointStyle: true } },
                  tooltip: { backgroundColor: "rgba(30,6,15,.95)", callbacks: { label: (c) => ` ${c.label}: ${formatBytes(c.parsed)}` } },
                },
              }}
            />
          </Box>
        </GlassCard>
        <GlassCard>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Uploads, last 14 days
          </Typography>
          <Box sx={{ height: 260 }}>
            <Bar
              data={{
                labels: data.uploads_timeline.map((p) => new Date(p.date + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" })),
                datasets: [{ label: "Files", data: data.uploads_timeline.map((p) => p.count), backgroundColor: "#b5384f", borderRadius: 8, maxBarThickness: 28 }],
              }}
              options={chartBase}
            />
          </Box>
        </GlassCard>
      </Box>

      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" } }}>
        <FileList title="Largest files" files={data.largest_files} metric={(f) => formatBytes(f.size_bytes)} />
        <FileList title="Recent uploads" files={data.recent_uploads} metric={(f) => formatDate(f.uploaded_at)} />
      </Box>
    </>
  );
}
