import React from 'react';

interface BrandMarkProps {
    variant?: 'full' | 'icon';
    size?: number;
    className?: string;
    showTitle?: boolean;
}

export default function BrandMark({ variant = 'full', size = 36, className = '', showTitle = true }: BrandMarkProps) {
    // Exact aiKart 'ai' emblem SVG path with smooth continuous ribbon
    const iconMark = (
        <svg
            width={size}
            height={size}
            viewBox="0 0 96 80"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{ display: 'block', flexShrink: 0 }}
        >
            {/* Smooth 'ai' ribbon stroke */}
            <path
                d="M 52 44 C 52 57 41 66 27 66 C 13 66 5 55 5 40 C 5 25 14 14 27 14 C 40 14 49 24 54 34 L 64 54 C 68 62 73 66 79 66 C 85 66 89 61 89 52 L 89 30"
                stroke="#0050FF"
                strokeWidth="10"
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
            />
            {/* Blue dot on top of 'i' stem */}
            <circle cx="89" cy="14" r="6.5" fill="#0050FF" />
        </svg>
    );

    if (variant === 'icon') {
        return <div className={`brand-mark-icon ${className}`}>{iconMark}</div>;
    }

    return (
        <div className={`brand-mark-full ${className}`} style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
            {iconMark}
            {showTitle && (
                <div style={{ display: 'flex', alignItems: 'center', lineHeight: 1 }}>
                    <span 
                        style={{ 
                            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif", 
                            fontWeight: 800, 
                            fontSize: '1.45rem', 
                            color: '#0f172a',
                            letterSpacing: '-0.03em',
                            display: 'flex',
                            alignItems: 'center',
                        }}
                    >
                        kart
                        <span 
                            style={{ 
                                fontSize: '0.72rem', 
                                fontWeight: 700, 
                                marginLeft: '8px', 
                                padding: '3px 10px', 
                                borderRadius: '9999px', 
                                backgroundColor: 'rgba(0, 80, 255, 0.08)', 
                                color: '#0050FF',
                                letterSpacing: '0.04em',
                                textTransform: 'uppercase'
                            }}
                        >
                            Healthcare AI
                        </span>
                    </span>
                </div>
            )}
        </div>
    );
}
