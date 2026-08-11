const UNITS = ["B", "KB", "MB", "GB", "TB"];

export function numberWithCommas(value: number | string): string {
  return String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    UNITS.length - 1,
  );
  const value = bytes / 1024 ** i;
  const display = value >= 100 ? Math.round(value) : value.toFixed(1);
  return `${numberWithCommas(display)} ${UNITS[i]}`;
}

export function formatBytesWithSuffix(bytes: number, suffix: string): string {
  if (bytes === 0) return `0 ${suffix}`;
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    UNITS.length - 1,
  );
  const value = bytes / 1024 ** i;
  const display = value >= 100 ? Math.round(value) : value.toFixed(1);
  return `${numberWithCommas(display)} ${UNITS[i]} ${suffix}`;
}
