const paths = {
  plus: <><path d="M12 5v14M5 12h14" /></>,
  message: <><path d="M20 11.5a7.5 7.5 0 0 1-8 7.5 8.8 8.8 0 0 1-3.1-.55L4 20l1.55-3.55A7.3 7.3 0 0 1 4 11.5 7.5 7.5 0 0 1 12 4a7.5 7.5 0 0 1 8 7.5Z" /><path d="M8 11.5h.01M12 11.5h.01M16 11.5h.01" /></>,
  book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21V5.5Z" /><path d="M4 18.5A2.5 2.5 0 0 1 6.5 16H20M8 7h8M8 10h6" /></>,
  chart: <><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M8 16v-3M12 16V8M16 16v-6" /></>,
  search: <><circle cx="10.8" cy="10.8" r="6.2" /><path d="m16 16 4 4" /></>,
  settings: <><path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z" /><path d="m19.4 15 .1.1a1.7 1.7 0 0 1-2.4 2.4l-.1-.1a1.7 1.7 0 0 0-2.9 1.2v.2a1.7 1.7 0 0 1-3.4 0v-.2a1.7 1.7 0 0 0-2.9-1.2l-.1.1a1.7 1.7 0 0 1-2.4-2.4l.1-.1A1.7 1.7 0 0 0 6.2 12a1.7 1.7 0 0 0-1.8-1.7 1.7 1.7 0 0 1 0-3.4h.2A1.7 1.7 0 0 0 5.8 4l-.1-.1a1.7 1.7 0 0 1 2.4-2.4l.1.1A1.7 1.7 0 0 0 11 0.4v-.2a1.7 1.7 0 0 1 3.4 0v.2A1.7 1.7 0 0 0 17.3 2l.1-.1a1.7 1.7 0 0 1 2.4 2.4l-.1.1A1.7 1.7 0 0 0 20.9 7h.2a1.7 1.7 0 0 1 0 3.4h-.2a1.7 1.7 0 0 0-1.5 2.9Z" transform="translate(-1.5 1.5) scale(.88)" /></>,
  bookmark: <><path d="M6 4.5A2.5 2.5 0 0 1 8.5 2H18a2 2 0 0 1 2 2v16l-6.5-3.5L7 20V5.5" /><path d="M4 6.5A2.5 2.5 0 0 1 6.5 4H18" /></>,
  clock: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3.5 2" /></>,
  send: <><path d="m21 3-7.4 18-3.2-7.4L3 10.4 21 3Z" /><path d="M10.4 13.6 21 3" /></>,
  copy: <><rect x="8" y="8" width="11" height="11" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></>,
  like: <path d="M7 20H4a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3m0 9h7.7a2 2 0 0 0 1.9-1.4l1.8-5.5A2 2 0 0 0 16.5 11H13l.6-3.2A2.4 2.4 0 0 0 11.2 5L7 11v9Z" />,
  dislike: <path d="M7 4H4a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h3m0-9h7.7a2 2 0 0 1 1.9 1.4l1.8 5.5A2 2 0 0 1 16.5 13H13l.6 3.2a2.4 2.4 0 0 1-2.4 2.8L7 13V4Z" />,
  shield: <><path d="M12 3 20 6v5.5c0 4.2-3 7.7-8 9.5-5-1.8-8-5.3-8-9.5V6l8-3Z" /><path d="m8.7 12 2.2 2.2 4.5-4.5" /></>,
  chevron: <path d="m9 6 6 6-6 6" />,
  down: <path d="m6 9 6 6 6-6" />,
  panel: <><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M16 4v16" /></>,
  x: <><path d="m6 6 12 12M18 6 6 18" /></>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
  alert: <><path d="m12 4 8 15H4L12 4Z" /><path d="M12 9v4M12 16h.01" /></>,
  check: <path d="m6 12 4 4 8-9" />,
  refresh: <><path d="M20 11a8 8 0 0 0-14.7-3L4 10" /><path d="M4 5v5h5M4 13a8 8 0 0 0 14.7 3L20 14" /><path d="M20 19v-5h-5" /></>,
  user: <><circle cx="12" cy="8" r="3.5" /><path d="M5 20a7 7 0 0 1 14 0" /></>,
  sparkle: <><path d="m12 3 1.2 5.8L19 10l-5.8 1.2L12 17l-1.2-5.8L5 10l5.8-1.2L12 3Z" /><path d="m19 16 .5 2.5L22 19l-2.5.5L19 22l-.5-2.5L16 19l2.5-.5L19 16Z" /></>,
};

export function Icon({ name, size = 18, strokeWidth = 1.8, className = "" }) {
  return (
    <svg
      aria-hidden="true"
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name] || paths.sparkle}
    </svg>
  );
}
