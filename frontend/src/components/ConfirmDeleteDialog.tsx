import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  List,
  ListItem,
  ListItemText,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { filesApi } from "../api/endpoints";
import { formatBytes } from "../api/format";
import type { DeletionPreview, DeletionResult } from "../api/types";

interface Props {
  open: boolean;
  fileIds: number[];
  onClose: () => void;
  onDeleted: (result: DeletionResult) => void;
}

/** Confirm the selected files, show the storage impact, block protected files. */
export default function ConfirmDeleteDialog({ open, fileIds, onClose, onDeleted }: Props) {
  const [preview, setPreview] = useState<DeletionPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [understood, setUnderstood] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setPreview(null);
    setError(null);
    setUnderstood(false);
    setReason("");
    let cancelled = false;
    filesApi
      .previewDeletion(fileIds)
      .then((p) => !cancelled && setPreview(p))
      .catch((e) => !cancelled && setError(errorMessage(e)));
    return () => {
      cancelled = true;
    };
  }, [open, fileIds]);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await filesApi.bulkDelete(fileIds, reason.trim() || undefined);
      onDeleted(result);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const protectedItems = preview?.items.filter((i) => i.is_protected) ?? [];

  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} fullWidth maxWidth="sm">
      <DialogTitle sx={{ pb: 1 }}>
        Delete {fileIds.length === 1 ? "this file" : `${fileIds.length} files`}?
      </DialogTitle>
      <DialogContent>
        {!preview && !error && (
          <Box sx={{ display: "grid", placeItems: "center", py: 5 }}>
            <CircularProgress color="secondary" />
          </Box>
        )}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        {preview && (
          <Stack spacing={2}>
            <Box className="glass" sx={{ p: 2, display: "flex", gap: 4, flexWrap: "wrap" }}>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Space freed
                </Typography>
                <Typography variant="h5" className="display-font">
                  {formatBytes(preview.total_bytes)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="body2" color="text.secondary">
                  Of which redundant copies
                </Typography>
                <Typography variant="h5" className="display-font" color="secondary">
                  {formatBytes(preview.redundant_bytes_removed)}
                </Typography>
              </Box>
            </Box>

            {protectedItems.length > 0 && (
              <Alert severity="error">
                Protected files can’t be deleted: {protectedItems.map((i) => i.filename).join(", ")}. Remove their protection
                first, or deselect them.
              </Alert>
            )}
            {preview.warnings.map((w) => (
              <Alert key={w} severity="warning">
                {w}
              </Alert>
            ))}

            <List dense disablePadding sx={{ maxHeight: 200, overflow: "auto" }}>
              {preview.items.map((i) => (
                <ListItem key={i.id} disableGutters divider>
                  <ListItemText
                    primary={i.filename}
                    secondary={`${formatBytes(i.size_bytes)} · ${
                      i.is_original ? "original" : i.is_duplicate ? "duplicate" : "unique file"
                    }${i.duplicate_group_id ? ` · ${i.copies_remaining} copies stay` : ""}`}
                    primaryTypographyProps={{ noWrap: true }}
                  />
                </ListItem>
              ))}
            </List>

            <TextField
              size="small"
              label="Reason (optional)"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              inputProps={{ maxLength: 255 }}
            />
            <FormControlLabel
              control={<Checkbox checked={understood} onChange={(e) => setUnderstood(e.target.checked)} color="secondary" />}
              label="I’ve checked the files above. Deleting them can’t be undone."
            />
          </Stack>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button onClick={onClose} disabled={busy} color="inherit">
          Keep files
        </Button>
        <Button
          variant="contained"
          onClick={submit}
          disabled={!preview || !preview.can_delete || !understood || busy}
          startIcon={busy ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          Delete {formatBytes(preview?.total_bytes ?? 0)}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
