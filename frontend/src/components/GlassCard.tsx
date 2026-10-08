import { Box, type BoxProps } from "@mui/material";

export default function GlassCard({ sx, className, ...rest }: BoxProps) {
  return <Box className={`glass ${className ?? ""}`} sx={{ p: { xs: 2, md: 3 }, ...sx }} {...rest} />;
}
