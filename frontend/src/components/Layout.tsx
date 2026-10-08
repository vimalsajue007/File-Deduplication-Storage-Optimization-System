import ContentCopyRoundedIcon from "@mui/icons-material/ContentCopyRounded";
import DashboardRoundedIcon from "@mui/icons-material/DashboardRounded";
import FolderRoundedIcon from "@mui/icons-material/FolderRounded";
import HistoryRoundedIcon from "@mui/icons-material/HistoryRounded";
import LogoutRoundedIcon from "@mui/icons-material/LogoutRounded";
import MenuRoundedIcon from "@mui/icons-material/MenuRounded";
import UploadFileRoundedIcon from "@mui/icons-material/UploadFileRounded";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Snackbar,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import { useCallback, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import type { UploadResponse } from "../api/types";
import { useAuth } from "../context/AuthContext";
import UploadDialog from "./UploadDialog";

const NAV = [
  { to: "/", label: "Dashboard", icon: <DashboardRoundedIcon /> },
  { to: "/files", label: "Files", icon: <FolderRoundedIcon /> },
  { to: "/duplicates", label: "Duplicates", icon: <ContentCopyRoundedIcon /> },
  { to: "/history", label: "History", icon: <HistoryRoundedIcon /> },
];

const DRAWER_WIDTH = 252;

export interface LayoutContext {
  refreshKey: number;
  refresh: () => void;
  openUpload: () => void;
}

function Brand() {
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, px: 1 }}>
      <Box
        sx={{
          width: 38,
          height: 38,
          borderRadius: "12px",
          background: "linear-gradient(135deg,#b5384f,#5a1226)",
          display: "grid",
          placeItems: "center",
          boxShadow: "inset 0 1px 0 rgba(255,255,255,.3), 0 6px 18px rgba(140,31,66,.5)",
        }}
      >
        <ContentCopyRoundedIcon sx={{ fontSize: 20, color: "#f7e6d2" }} />
      </Box>
      <Typography variant="h6" className="display-font" sx={{ letterSpacing: "-0.01em" }}>
        Dedupe
      </Typography>
    </Box>
  );
}

export default function Layout() {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("md"));
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuEl, setMenuEl] = useState<HTMLElement | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [toast, setToast] = useState<{ message: string; severity: "success" | "warning" } | null>(null);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);
  const openUpload = useCallback(() => setUploadOpen(true), []);

  const onUploaded = (res: UploadResponse) => {
    refresh();
    const n = res.uploaded.length;
    setToast({
      severity: res.queued ? "success" : "warning",
      message: res.queued
        ? `${n} file${n > 1 ? "s" : ""} uploaded. Duplicate check is running in the background.`
        : `${n} file${n > 1 ? "s" : ""} uploaded, but the background worker is unavailable. Use Re-scan later.`,
    });
  };

  const drawer = (
    <Box sx={{ display: "flex", flexDirection: "column", height: "100%", p: 2 }}>
      <Brand />
      <List sx={{ mt: 4, display: "grid", gap: 0.5 }}>
        {NAV.map((item) => {
          const active = item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to);
          return (
            <ListItemButton
              key={item.to}
              component={NavLink}
              to={item.to}
              onClick={() => setMobileOpen(false)}
              selected={active}
              sx={{
                borderRadius: 3,
                "&.Mui-selected": {
                  background: "linear-gradient(135deg, rgba(168,42,77,.55), rgba(123,30,58,.35))",
                  boxShadow: "inset 0 1px 0 rgba(255,255,255,.18)",
                },
              }}
            >
              <ListItemIcon sx={{ minWidth: 40, color: active ? "secondary.main" : "text.secondary" }}>{item.icon}</ListItemIcon>
              <ListItemText primary={item.label} primaryTypographyProps={{ fontWeight: active ? 700 : 500 }} />
            </ListItemButton>
          );
        })}
      </List>
      <Box sx={{ flex: 1 }} />
      <Button variant="contained" fullWidth startIcon={<UploadFileRoundedIcon />} onClick={openUpload} sx={{ py: 1.2 }}>
        Upload files
      </Button>
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      {isDesktop ? (
        <Box
          component="nav"
          aria-label="Main"
          className="glass"
          sx={{ position: "fixed", top: 16, left: 16, bottom: 16, width: DRAWER_WIDTH, borderRadius: "24px", zIndex: 10 }}
        >
          {drawer}
        </Box>
      ) : (
        <Drawer
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
          PaperProps={{ className: "glass-strong", sx: { width: DRAWER_WIDTH, borderRadius: "0 24px 24px 0" } }}
        >
          {drawer}
        </Drawer>
      )}

      <Box component="main" sx={{ flex: 1, minWidth: 0, ml: { md: `${DRAWER_WIDTH + 32}px` }, p: { xs: 2, md: 3 }, pr: { md: 4 } }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: { xs: "space-between", md: "flex-end" }, mb: 2 }}>
          {!isDesktop && (
            <IconButton aria-label="Open navigation" onClick={() => setMobileOpen(true)}>
              <MenuRoundedIcon />
            </IconButton>
          )}
          <Box>
            <Button
              onClick={(e) => setMenuEl(e.currentTarget)}
              color="inherit"
              startIcon={
                <Avatar sx={{ width: 30, height: 30, bgcolor: "primary.dark", fontSize: 14 }}>
                  {user?.username.slice(0, 1).toUpperCase()}
                </Avatar>
              }
            >
              {user?.username}
            </Button>
            <Menu anchorEl={menuEl} open={!!menuEl} onClose={() => setMenuEl(null)}>
              <MenuItem disabled sx={{ opacity: "1 !important" }}>
                <Typography variant="body2" color="text.secondary">
                  {user?.email}
                </Typography>
              </MenuItem>
              <MenuItem
                onClick={() => {
                  setMenuEl(null);
                  logout();
                  navigate("/login");
                }}
              >
                <ListItemIcon>
                  <LogoutRoundedIcon fontSize="small" />
                </ListItemIcon>
                Sign out
              </MenuItem>
            </Menu>
          </Box>
        </Box>
        <Outlet context={{ refreshKey, refresh, openUpload } satisfies LayoutContext} />
      </Box>

      <UploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} onUploaded={onUploaded} />
      <Snackbar open={!!toast} autoHideDuration={6000} onClose={() => setToast(null)} anchorOrigin={{ vertical: "bottom", horizontal: "center" }}>
        {toast ? (
          <Alert severity={toast.severity} variant="filled" onClose={() => setToast(null)}>
            {toast.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </Box>
  );
}
