import { Chip, CircularProgress } from "@mui/material";
import LockRoundedIcon from "@mui/icons-material/LockRounded";
import type { FileItem } from "../api/types";

export function StatusChip({ file }: { file: Pick<FileItem, "status" | "status_message"> }) {
  switch (file.status) {
    case "ready":
      return <Chip size="small" label="Scanned" color="success" variant="outlined" />;
    case "failed":
      return <Chip size="small" label="Failed" color="error" variant="outlined" title={file.status_message ?? undefined} />;
    default:
      return (
        <Chip
          size="small"
          label={file.status === "processing" ? "Hashing" : "Queued"}
          color="warning"
          variant="outlined"
          icon={<CircularProgress size={12} color="warning" />}
        />
      );
  }
}

export function ProtectedChip() {
  return <Chip size="small" icon={<LockRoundedIcon />} label="Protected" color="secondary" variant="outlined" />;
}
