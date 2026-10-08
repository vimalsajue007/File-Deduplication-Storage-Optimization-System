export type FileCategory = "image" | "video" | "audio" | "document" | "archive" | "code" | "other";
export type FileStatus = "pending" | "processing" | "ready" | "failed";
export type DuplicateFilter = "all" | "any" | "copies" | "unique";

export interface User {
  id: number;
  email: string;
  username: string;
  is_admin: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface FileItem {
  id: number;
  original_filename: string;
  size_bytes: number;
  mime_type: string;
  extension: string;
  category: FileCategory;
  status: FileStatus;
  status_message: string | null;
  is_protected: boolean;
  is_duplicate: boolean;
  duplicate_group_id: number | null;
  content_hash: string | null;
  uploaded_at: string;
  processed_at: string | null;
}

export interface FileMetadata {
  extension: string;
  declared_mime: string | null;
  detected_mime: string;
  signature: string | null;
  is_text: boolean;
  extra: Record<string, unknown> | null;
}

export interface GroupBrief {
  id: number;
  file_count: number;
  original_file_id: number | null;
  original_filename: string | null;
  potential_savings: number;
}

export interface FileDetail extends FileItem {
  file_metadata: FileMetadata | null;
  group: GroupBrief | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface UploadResponse {
  uploaded: FileItem[];
  rejected: { filename: string; reason: string }[];
  queued: boolean;
}

export interface FileQuery {
  q?: string;
  file_type?: FileCategory;
  min_size?: number;
  max_size?: number;
  duplicates?: DuplicateFilter;
  uploaded_from?: string;
  uploaded_to?: string;
  sort_by: "name" | "size" | "uploaded_at" | "type";
  sort_order: "asc" | "desc";
  page: number;
  page_size: number;
}

export interface DuplicateGroup {
  id: number;
  content_hash: string;
  file_size: number;
  file_count: number;
  total_storage: number;
  potential_savings: number;
  original: FileItem | null;
  duplicates: FileItem[];
  created_at: string;
  updated_at: string;
}

export interface DeletionPreviewItem {
  id: number;
  filename: string;
  size_bytes: number;
  is_protected: boolean;
  is_duplicate: boolean;
  is_original: boolean;
  duplicate_group_id: number | null;
  copies_remaining: number;
}

export interface DeletionPreview {
  items: DeletionPreviewItem[];
  total_bytes: number;
  redundant_bytes_removed: number;
  protected_ids: number[];
  warnings: string[];
  can_delete: boolean;
}

export interface DeletionResult {
  deleted_ids: number[];
  deleted_count: number;
  freed_bytes: number;
  redundant_bytes_removed: number;
  skipped_protected_ids: number[];
}

export interface DeletionHistoryItem {
  id: number;
  file_id: number | null;
  filename: string;
  size_bytes: number;
  content_hash: string | null;
  category: string;
  was_duplicate: boolean;
  was_original: boolean;
  duplicate_group_id: number | null;
  reason: string | null;
  deleted_at: string;
}

export interface AuditLogItem {
  id: number;
  user_id: number | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  ip_address: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface Analytics {
  total_files: number;
  total_storage: number;
  duplicate_files: number;
  files_in_duplicate_groups: number;
  duplicate_groups: number;
  duplicate_storage: number;
  potential_savings: number;
  savings_percent: number;
  pending_files: number;
  storage_by_category: { category: string; count: number; bytes: number }[];
  uploads_timeline: { date: string; count: number; bytes: number }[];
  largest_files: FileItem[];
  recent_uploads: FileItem[];
}
