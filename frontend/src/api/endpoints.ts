import { api } from "./client";
import type {
  Analytics,
  AuditLogItem,
  DeletionHistoryItem,
  DeletionPreview,
  DeletionResult,
  DuplicateGroup,
  FileDetail,
  FileItem,
  FileQuery,
  Page,
  TokenResponse,
  UploadResponse,
  User,
} from "./types";

export const authApi = {
  login: (username: string, password: string) =>
    api
      .post<TokenResponse>("/auth/login", new URLSearchParams({ username, password }), {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      })
      .then((r) => r.data),
  register: (email: string, username: string, password: string) =>
    api.post<User>("/auth/register", { email, username, password }).then((r) => r.data),
  me: () => api.get<User>("/auth/me").then((r) => r.data),
};

export const filesApi = {
  list: (params: FileQuery) => api.get<Page<FileItem>>("/files", { params }).then((r) => r.data),
  get: (id: number) => api.get<FileDetail>(`/files/${id}`).then((r) => r.data),
  upload: (files: File[], onProgress?: (percent: number) => void) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return api
      .post<UploadResponse>("/files/upload", form, {
        timeout: 0, // large files can take a while
        onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
      })
      .then((r) => r.data);
  },
  download: async (file: Pick<FileItem, "id" | "original_filename">) => {
    const res = await api.get<Blob>(`/files/${file.id}/download`, { responseType: "blob", timeout: 0 });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.original_filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
  setProtection: (id: number, is_protected: boolean) =>
    api.patch<FileItem>(`/files/${id}/protection`, { is_protected }).then((r) => r.data),
  reprocess: (id: number) => api.post<FileItem>(`/files/${id}/reprocess`).then((r) => r.data),
  previewDeletion: (file_ids: number[]) =>
    api.post<DeletionPreview>("/files/deletion-preview", { file_ids }).then((r) => r.data),
  bulkDelete: (file_ids: number[], reason?: string) =>
    api.post<DeletionResult>("/files/bulk-delete", { file_ids, confirm: true, reason }).then((r) => r.data),
};

export const duplicatesApi = {
  groups: (params: { sort_by: string; page: number; page_size: number }) =>
    api.get<Page<DuplicateGroup>>("/duplicates/groups", { params }).then((r) => r.data),
  rescan: () => api.post<{ queued: boolean }>("/duplicates/rescan").then((r) => r.data),
};

export const analyticsApi = {
  summary: () => api.get<Analytics>("/analytics/summary").then((r) => r.data),
};

export const historyApi = {
  deletions: (page: number, page_size: number) =>
    api.get<Page<DeletionHistoryItem>>("/history/deletions", { params: { page, page_size } }).then((r) => r.data),
  audit: (page: number, page_size: number) =>
    api.get<Page<AuditLogItem>>("/history/audit", { params: { page, page_size } }).then((r) => r.data),
};
