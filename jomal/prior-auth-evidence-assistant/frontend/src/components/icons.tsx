import React from 'react';

type IconProps = React.SVGProps<SVGSVGElement>;

const base = {
    width: 18,
    height: 18,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
};

export const IconCases: React.FC<IconProps> = (props) => (
    <svg {...base} {...props}>
        <path d="M9 4h6l1 3h4a1 1 0 0 1 1 1v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a1 1 0 0 1 1-1h4z" />
        <path d="M8 12h8M8 16h5" />
    </svg>
);

export const IconNurse: React.FC<IconProps> = (props) => (
    <svg {...base} {...props}>
        <path d="M9 3v4a3 3 0 0 0 6 0V3" />
        <path d="M6 3v5a6 6 0 0 0 12 0V3" />
        <circle cx="18" cy="17" r="3" />
        <path d="M12 14v3" />
    </svg>
);

export const IconAdmin: React.FC<IconProps> = (props) => (
    <svg {...base} {...props}>
        <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" />
        <path d="m9 12 2 2 4-4" />
    </svg>
);

export const IconPolicy: React.FC<IconProps> = (props) => (
    <svg {...base} {...props}>
        <path d="M6 4h9l3 3v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z" />
        <path d="M14 4v3a1 1 0 0 0 1 1h3" />
        <path d="M8 13h8M8 17h5" />
    </svg>
);

export const IconLogout: React.FC<IconProps> = (props) => (
    <svg {...base} {...props}>
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
        <path d="M16 17l5-5-5-5" />
        <path d="M21 12H9" />
    </svg>
);

export const IconUpload: React.FC<IconProps> = (props) => (
    <svg {...base} {...props}>
        <path d="M12 16V4" />
        <path d="m7 9 5-5 5 5" />
        <path d="M5 20h14" />
    </svg>
);

export const IconCheckCircle: React.FC<IconProps> = (props) => (
    <svg {...base} {...props}>
        <circle cx="12" cy="12" r="9" />
        <path d="m8.5 12.5 2.3 2.3L15.5 9.5" />
    </svg>
);

export const IconAlert: React.FC<IconProps> = (props) => (
    <svg {...base} {...props}>
        <path d="M12 9v4" />
        <path d="M10.3 3.9 2.7 17.3A1.5 1.5 0 0 0 4 19.5h16a1.5 1.5 0 0 0 1.3-2.2L13.7 3.9a1.5 1.5 0 0 0-2.6 0z" />
        <path d="M12 16.5h.01" />
    </svg>
);

export const IconFile: React.FC<IconProps> = (props) => (
    <svg {...base} {...props}>
        <path d="M6 3h8l4 4v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
        <path d="M13 3v4a1 1 0 0 0 1 1h4" />
    </svg>
);

export const IconInbox: React.FC<IconProps> = (props) => (
    <svg {...base} {...props}>
        <path d="M3 12h4l2 3h6l2-3h4" />
        <path d="M5 12 6.5 5.5A2 2 0 0 1 8.45 4h7.1a2 2 0 0 1 1.95 1.5L19 12v6a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2z" />
    </svg>
);

export const IconLock: React.FC<IconProps> = (props) => (
    <svg {...base} {...props}>
        <rect x="5" y="11" width="14" height="9" rx="2" />
        <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
);

export const IconChevronRight: React.FC<IconProps> = (props) => (
    <svg {...base} {...props}>
        <path d="m9 6 6 6-6 6" />
    </svg>
);
