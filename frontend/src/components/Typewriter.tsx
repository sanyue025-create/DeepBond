
'use client';

import { useState, useEffect } from 'react';

interface TypewriterProps {
    text: string;
    speed?: number; // ms per char
    onComplete?: () => void;
}

export default function Typewriter({ text, speed = 20, onComplete }: TypewriterProps) {
    const [displayedText, setDisplayedText] = useState('');

    useEffect(() => {
        let index = 0;
        const intervalId = setInterval(() => {
            setDisplayedText((prev) => {
                if (index >= text.length) {
                    clearInterval(intervalId);
                    if (onComplete) onComplete();
                    return text;
                }
                return text.slice(0, index + 1);
            });
            index++;
        }, speed);

        return () => clearInterval(intervalId);
    }, [text, speed, onComplete]);

    return <span>{displayedText}</span>;
}
