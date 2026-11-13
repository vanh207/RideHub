/* ==========================================================================
   RideHub Custom Duotone SVG Icon System (js/auth/icons.js)
   Usage: icon('shield-check') -> returns inline SVG string
   ========================================================================== */

const ICON_PATHS = {
  'arrow-left': '<path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
  'arrow-right': '<path d="M5 12h14M12 5l7 7-7 7" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
  'eye': '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" fill="var(--green-100)" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>',
  'eye-off': '<path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-6.5 0-10-7-10-7a18.5 18.5 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c6.5 0 10 7 10 7a18.5 18.5 0 0 1-2.16 3.19M3 3l18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  'shield-check': '<path d="M12 2l7 3.5v6c0 5-3.2 9.2-7 10.5-3.8-1.3-7-5.5-7-10.5v-6L12 2z" fill="var(--green-100)" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M9 12l2 2 4-4" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
  'lock': '<rect x="5" y="11" width="14" height="10" rx="3" fill="var(--green-100)" stroke="currentColor" stroke-width="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  'user': '<circle cx="12" cy="8" r="4" fill="var(--green-100)" stroke="currentColor" stroke-width="2"/><path d="M4 20c1.5-3.8 4.8-5.5 8-5.5s6.5 1.7 8 5.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  'store': '<path d="M3 9l2-5h14l2 5v2a3 3 0 0 1-6 0 3 3 0 0 1-6 0 3 3 0 0 1-6 0V9z" fill="var(--green-100)" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M5 14v6h14v-6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  'upload': '<path d="M12 16V4M7 9l5-5 5 5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  'check': '<circle cx="12" cy="12" r="9" fill="var(--green-100)" stroke="currentColor" stroke-width="2"/><path d="M8.5 12.5l2.5 2.5 4.5-5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
  'alert': '<circle cx="12" cy="12" r="9" fill="#fff1f2" stroke="currentColor" stroke-width="2"/><path d="M12 8v5M12 16.5h.01" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
  'rotate': '<path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  'zoom-in': '<circle cx="11" cy="11" r="7" fill="var(--green-100)" stroke="currentColor" stroke-width="2"/><path d="M21 21l-4.35-4.35M11 8v6M8 11h6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  'copy': '<rect x="9" y="9" width="11" height="11" rx="2" fill="var(--green-100)" stroke="currentColor" stroke-width="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke="currentColor" stroke-width="2"/>',
  'key': '<circle cx="8" cy="15" r="4" fill="var(--green-100)" stroke="currentColor" stroke-width="2"/><path d="M11 12l9-9M17 6l3 3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  'chat': '<path d="M21 12c0 4.4-4 8-9 8-1.4 0-2.8-.3-4-.8L3 20l1.3-3.6C3.5 15.1 3 13.6 3 12c0-4.4 4-8 9-8s9 3.6 9 8z" fill="var(--green-100)" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
  'bell': '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" fill="var(--green-100)" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M10.3 21a2 2 0 0 0 3.4 0" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  'log-out': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
};

export function icon(name, cls = 'rh-icon') {
  const body = ICON_PATHS[name] || ICON_PATHS['check'];
  return `<svg class="${cls}" viewBox="0 0 24 24" fill="none" aria-hidden="true">${body}</svg>`;
}

export function hydrateIcons(root = document) {
  root.querySelectorAll('[data-icon]').forEach((el) => {
    const name = el.getAttribute('data-icon');
    const cls = el.getAttribute('data-icon-class') || 'rh-icon';
    el.innerHTML = icon(name, cls);
  });
}

