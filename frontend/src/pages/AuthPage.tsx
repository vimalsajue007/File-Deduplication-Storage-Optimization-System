import { Alert, Box, Button, CircularProgress, Link, Stack, TextField, Typography } from "@mui/material";
import { useState, type FormEvent } from "react";
import { Link as RouterLink, Navigate, useLocation, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { token, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [identity, setIdentity] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";

  if (token) return <Navigate to="/" replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (isLogin) await login(identity, password);
      else await register(email, identity, password);
      navigate((location.state as { from?: string } | null)?.from ?? "/", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box sx={{ minHeight: "100vh", display: "grid", gridTemplateColumns: { xs: "1fr", md: "1.1fr 1fr" }, alignItems: "center", gap: 6, p: { xs: 2, md: 8 } }}>
      <Box sx={{ display: { xs: "none", md: "block" }, maxWidth: 520 }}>
        <Typography variant="h2" sx={{ fontSize: { md: 52, lg: 60 }, lineHeight: 1.05, letterSpacing: "-0.02em" }}>
          Find the files you’ve saved twice.
        </Typography>
        <Typography sx={{ mt: 3, fontSize: 18, color: "text.secondary", lineHeight: 1.6 }}>
          Dedupe compares what’s inside your files, not what they’re called, then shows exactly how much space you can get back before you
          delete anything.
        </Typography>
      </Box>

      <Box className="glass-strong" component="form" onSubmit={submit} sx={{ p: { xs: 3, md: 5 }, borderRadius: "28px", width: "100%", maxWidth: 460, justifySelf: "center" }}>
        <Typography variant="h5" sx={{ mb: 0.5 }}>
          {isLogin ? "Sign in" : "Create your account"}
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          {isLogin ? "Use your email or username." : "Your files stay private to your account."}
        </Typography>
        <Stack spacing={2}>
          {error && <Alert severity="error">{error}</Alert>}
          {!isLogin && (
            <TextField label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          )}
          <TextField
            label={isLogin ? "Email or username" : "Username"}
            value={identity}
            onChange={(e) => setIdentity(e.target.value)}
            required
            autoComplete="username"
            autoFocus
            inputProps={!isLogin ? { minLength: 3, maxLength: 32, pattern: "[A-Za-z0-9_.\\-]+" } : undefined}
          />
          <TextField
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete={isLogin ? "current-password" : "new-password"}
            helperText={!isLogin ? "At least 8 characters, with a letter and a number." : undefined}
            inputProps={!isLogin ? { minLength: 8 } : undefined}
          />
          <Button type="submit" variant="contained" size="large" disabled={busy} startIcon={busy ? <CircularProgress size={18} color="inherit" /> : undefined}>
            {isLogin ? "Sign in" : "Create account"}
          </Button>
          <Typography variant="body2" color="text.secondary" textAlign="center">
            {isLogin ? "New here? " : "Already registered? "}
            <Link component={RouterLink} to={isLogin ? "/register" : "/login"} color="secondary" underline="hover">
              {isLogin ? "Create an account" : "Sign in"}
            </Link>
          </Typography>
        </Stack>
      </Box>
    </Box>
  );
}
