import CloudUploadRoundedIcon from "@mui/icons-material/CloudUploadRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, LinearProgress, Stack, Typography } from "@mui/material";
import { useRef, useState, type DragEvent } from "react";
import { errorDetails, errorMessage } from "../api/client";
import { filesApi } from "../api/endpoints";
import { formatBytes } from "../api/format";
import type { UploadResponse } from "../api/types";

interface Props {
  open: boolean;
  onClose: () => void;
  onUploaded: (res: UploadResponse) => void;
}

export default function UploadDialog({ open, onClose, onUploaded }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rejected, setRejected] = useState<{ filename: string; reason: string }[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const busy = progress !== null;

  const reset = () => {
    setFiles([]);
    setProgress(null);
    setError(null);
    setRejected([]);
  };
  const close = () => {
    if (busy) return;
    reset();
    onClose();
  };

  const add = (list: FileList | null) => {
    if (!list) return;
    setFiles((prev) => [...prev, ...Array.from(list)]);
    setError(null);
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    add(e.dataTransfer.files);
  };

  const submit = async () => {
    setProgress(0);
    setError(null);
    setRejected([]);
    try {
      const res = await filesApi.upload(files, setProgress);
      onUploaded(res);
      if (res.rejected.length) {
        setRejected(res.rejected);
        setFiles([]);
        setProgress(null);
      } else {
        reset();
        onClose();
      }
    } catch (e) {
      const details = errorDetails<{ rejected?: { filename: string; reason: string }[] }>(e);
      if (details?.rejected?.length) setRejected(details.rejected);
      else setError(errorMessage(e));
      setProgress(null);
    }
  };

  const total = files.reduce((s, f) => s + f.size, 0);

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="sm">
      <DialogTitle>Upload files</DialogTitle>
      <DialogContent>
        <Box
          role="button"
          tabIndex={0}
          onClick={() => input.current?.click()}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          sx={{
            border: "1.5px dashed",
            borderColor: dragging ? "secondary.main" : "rgba(255,255,255,0.28)",
            background: dragging ? "rgba(233,207,174,0.1)" : "rgba(255,255,255,0.04)",
            borderRadius: 4,
            p: 4,
            textAlign: "center",
            cursor: "pointer",
            transition: "all .2s",
          }}
        >
          <CloudUploadRoundedIcon sx={{ fontSize: 40, color: "secondary.main" }} />
          <Typography sx={{ mt: 1, fontWeight: 600 }}>Drop files here or click to browse</Typography>
          <Typography variant="body2" color="text.secondary">
            Duplicates are found after upload, whatever the file is called.
          </Typography>
          <input ref={input} type="file" multiple hidden onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
        </Box>

        {files.length > 0 && (
          <Stack spacing={0.5} sx={{ mt: 2, maxHeight: 180, overflow: "auto" }}>
            {files.map((f, i) => (
              <Box key={`${f.name}-${i}`} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Typography noWrap sx={{ flex: 1 }}>
                  {f.name}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {formatBytes(f.size)}
                </Typography>
                <IconButton size="small" aria-label={`Remove ${f.name}`} disabled={busy} onClick={() => setFiles(files.filter((_, j) => j !== i))}>
                  <CloseRoundedIcon fontSize="small" />
                </IconButton>
              </Box>
            ))}
          </Stack>
        )}

        {busy && (
          <Box sx={{ mt: 2 }}>
            <LinearProgress variant="determinate" value={progress ?? 0} color="secondary" />
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Uploading {formatBytes(total)} — {progress}%
            </Typography>
          </Box>
        )}
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
        {rejected.length > 0 && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            <Typography sx={{ fontWeight: 600 }}>Some files were not accepted</Typography>
            {rejected.map((r) => (
              <Typography key={r.filename} variant="body2">
                {r.filename}: {r.reason}
              </Typography>
            ))}
          </Alert>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button color="inherit" onClick={close} disabled={busy}>
          {rejected.length ? "Close" : "Cancel"}
        </Button>
        <Button variant="contained" onClick={submit} disabled={!files.length || busy}>
          Upload {files.length ? `${files.length} file${files.length > 1 ? "s" : ""}` : ""}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
