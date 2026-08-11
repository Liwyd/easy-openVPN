export async function copyToClipboard(text: string): Promise<void> {
  // navigator.clipboard requires HTTPS or localhost — fall back to
  // the older execCommand approach for plain-HTTP environments.
  if (window.isSecureContext && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}
