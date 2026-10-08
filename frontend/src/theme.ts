import { createTheme } from "@mui/material/styles";

const glassField = {
  background: "rgba(255,255,255,0.06)",
  backdropFilter: "blur(10px)",
  borderRadius: 12,
};

export const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#c9506b", dark: "#7b1e3a", light: "#e08aa0", contrastText: "#fff" },
    secondary: { main: "#e9cfae" },
    error: { main: "#ff7a8a" },
    warning: { main: "#f0b46a" },
    success: { main: "#8fd1a4" },
    text: { primary: "#f7ebe8", secondary: "#c9a9ad" },
    background: { default: "#12040a", paper: "#240812" },
    divider: "rgba(255,255,255,0.1)",
  },
  shape: { borderRadius: 14 },
  typography: {
    fontFamily: '"Manrope", system-ui, sans-serif',
    h1: { fontFamily: '"Fraunces", Georgia, serif', fontWeight: 600 },
    h2: { fontFamily: '"Fraunces", Georgia, serif', fontWeight: 600 },
    h3: { fontFamily: '"Fraunces", Georgia, serif', fontWeight: 600 },
    h4: { fontFamily: '"Fraunces", Georgia, serif', fontWeight: 600, letterSpacing: "-0.01em" },
    h5: { fontFamily: '"Fraunces", Georgia, serif', fontWeight: 600 },
    h6: { fontFamily: '"Fraunces", Georgia, serif', fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600, letterSpacing: 0 },
  },
  components: {
    MuiCssBaseline: { styleOverrides: { body: { backgroundColor: "#12040a" } } },
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 12, paddingInline: 18 },
        containedPrimary: {
          background: "linear-gradient(135deg, #8c1f42 0%, #b5384f 100%)",
          boxShadow: "0 6px 20px rgba(140,31,66,0.45), inset 0 1px 0 rgba(255,255,255,0.25)",
          "&:hover": { background: "linear-gradient(135deg, #a02450 0%, #c9506b 100%)" },
          "&.Mui-disabled": { background: "rgba(255,255,255,0.08)", boxShadow: "none" },
        },
        outlined: { borderColor: "rgba(255,255,255,0.22)", background: "rgba(255,255,255,0.04)" },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          ...glassField,
          "& fieldset": { borderColor: "rgba(255,255,255,0.16)" },
          "&:hover fieldset": { borderColor: "rgba(233,207,174,0.5)" },
          "&.Mui-focused fieldset": { borderColor: "#e9cfae" },
        },
      },
    },
    MuiDialog: {
      defaultProps: { PaperProps: { className: "glass-strong" } },
      styleOverrides: { paper: { borderRadius: 24 } },
    },
    MuiDrawer: { styleOverrides: { paper: { backgroundImage: "none" } } },
    MuiMenu: {
      styleOverrides: {
        paper: {
          background: "rgba(40,8,20,0.85)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255,255,255,0.14)",
          borderRadius: 14,
        },
      },
    },
    MuiPopover: {
      styleOverrides: {
        paper: {
          background: "rgba(40,8,20,0.88)",
          backdropFilter: "blur(20px)",
          border: "1px solid rgba(255,255,255,0.14)",
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: { borderBottom: "1px solid rgba(255,255,255,0.07)" },
        head: { color: "#c9a9ad", fontWeight: 600, background: "transparent" },
      },
    },
    MuiTableRow: { styleOverrides: { root: { "&.Mui-selected, &.Mui-selected:hover": { background: "rgba(201,80,107,0.16)" } } } },
    MuiChip: { styleOverrides: { root: { fontWeight: 600, backdropFilter: "blur(8px)" } } },
    MuiTooltip: { styleOverrides: { tooltip: { background: "rgba(30,6,15,0.95)", border: "1px solid rgba(255,255,255,0.14)" } } },
    MuiLinearProgress: { styleOverrides: { root: { borderRadius: 8, background: "rgba(255,255,255,0.1)" } } },
    MuiAlert: { styleOverrides: { root: { borderRadius: 14, backdropFilter: "blur(10px)" } } },
  },
});
