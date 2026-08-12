export const LIFETIME = 31556952;

export function relativeTime(date: Date | string | number): string {
  const now = new Date();
  const then = new Date(date);
  const diff = then.getTime() - now.getTime();
  const seconds = Math.round(Math.abs(diff) / 1000);

  const minute = 60;
  const hour = minute * 60;
  const day = hour * 24;
  const month = day * 30;
  const year = month * 12;

  let amount: number;
  let unit: string;

  if (seconds < minute) {
    amount = seconds;
    unit = "second";
  } else if (seconds < hour) {
    amount = Math.floor(seconds / minute);
    unit = "minute";
  } else if (seconds < day) {
    amount = Math.floor(seconds / hour);
    unit = "hour";
  } else if (seconds < month) {
    amount = Math.floor(seconds / day);
    unit = "day";
  } else if (seconds < year) {
    amount = Math.floor(seconds / month);
    unit = "month";
  } else {
    amount = Math.floor(seconds / year);
    unit = "year";
  }

  const plural = amount === 1 ? "" : "s";
  return diff < 0
    ? `${amount} ${unit}${plural} ago`
    : `in ${amount} ${unit}${plural}`;
}

export function formatDate(date: Date | string | null): string {
  if (!date) return "\u2014";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(date));
}

export function formatTime(time: string | null): string {
  if (!time) return "\u2014";
  return time.length >= 5 ? time.slice(0, 5) : time;
}

export function formatUptime(seconds: number): string {
  if (!seconds || seconds <= 0) return "\u2014";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  return parts.join(" ") || "0m";
}
