'use client';

import { useEffect, useRef } from 'react';

interface AtomicCoreProps {
    isThinking: boolean;
    phase?: string; // idle, memory, thinking, decision, profile
}

interface Particle {
    x: number;
    y: number;
    vx: number;
    vy: number;
    radius: number;
    baseRadius: number;
    angle: number;
    offset: number; // For noise offset
}

const lerp = (start: number, end: number, t: number) => {
    return start * (1 - t) + end * t;
};

export default function AtomicCore({ isThinking, phase = 'idle' }: AtomicCoreProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    const phaseRef = useRef(phase);
    useEffect(() => { phaseRef.current = phase; }, [phase]);

    // Physics Parameters (Lerp Targets)
    const paramsRef = useRef({
        speedMult: 0.1,
        cohesion: 0.01,
        separation: 0.0,
        chaos: 0.0,
        pulseMag: 0.0,
        radiusScale: 1.0,
        swirl: 0.0
    });

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        let animationFrameId: number;
        let particles: Particle[] = [];
        const particleCount = 18; // More density for clumping

        const initParticles = (width: number, height: number) => {
            particles = [];
            for (let i = 0; i < particleCount; i++) {
                particles.push({
                    x: width / 2 + (Math.random() - 0.5) * 40,
                    y: height / 2 + (Math.random() - 0.5) * 40,
                    vx: 0,
                    vy: 0,
                    radius: 25 + Math.random() * 20,
                    baseRadius: 25 + Math.random() * 25,
                    angle: Math.random() * Math.PI * 2,
                    offset: Math.random() * 100
                });
            }
        };

        const render = () => {
            if (canvas.width !== canvas.offsetWidth || canvas.height !== canvas.offsetHeight) {
                canvas.width = canvas.offsetWidth;
                canvas.height = canvas.offsetHeight;
                initParticles(canvas.width, canvas.height);
            }

            const width = canvas.width;
            const height = canvas.height;
            const centerX = width / 2;
            const centerY = height / 2;

            if (particles.length === 0) initParticles(width, height);

            ctx.clearRect(0, 0, width, height);

            // 1. Define Target States
            const currentPhase = phaseRef.current || 'idle';
            let target = {
                speed: 0.1,    // Overall movement speed
                cohesion: 0.01, // Pull to center (Clumping)
                separation: 0.0, // Push apart (Spreading)
                chaos: 0.0,    // Random jitter
                pulse: 0.0,    // Heartbeat
                radius: 1.0,   // Bloat factor
                swirl: 0.0     // Rotation
            };

            switch (currentPhase) {
                case 'idle':
                    // [平时状态] 抱团、极慢、微小呼吸
                    target.speed = 3;      // 整体游走速度 (越小越安静)
                    target.cohesion = 0.006; // 抱团粘性 (越大吸得越紧)
                    target.separation = 0.03; // 排斥力 (越大散得越开)
                    target.swirl = 0.001;    // 旋转力
                    break;

                case 'thinking':
                    // [思考状态] 优雅流动，像搅拌浓稠液体
                    target.speed = 0.35;     // 活跃时的速度
                    target.cohesion = 0.008; // 保持链接，不要散架
                    target.separation = 0.13; // 轻微散开，增加透气感
                    target.chaos = 0.3;      // 随机抖动 (神经质程度)
                    target.swirl = 0.006;     // 旋转加速
                    break;

                case 'memory':
                    // [回忆状态] 向内坍缩聚焦
                    target.speed = 0.4;
                    target.cohesion = 0.06;  // 极强引力
                    target.radius = 0.6;     // 整体缩小
                    break;

                case 'decision':
                    // [决策状态] 缓慢沉重地搏动
                    target.speed = 0.15;
                    target.cohesion = 0.01;
                    target.pulse = 0.9;      // 心跳幅度
                    break;

                case 'profile':
                    // [画像更新] 膨胀、流动
                    target.speed = 0.3;
                    target.radius = 0.8;     // 整体变大
                    target.separation = 0.06;
                    target.swirl = 0.006;
                    break;
            }

            // 2. Lerp Params
            const p = paramsRef.current;
            const smooth = 0.03; // Even slower transitions
            p.speedMult = lerp(p.speedMult, target.speed, smooth);
            p.cohesion = lerp(p.cohesion, target.cohesion, smooth);
            p.separation = lerp(p.separation, target.separation, smooth);
            p.chaos = lerp(p.chaos, target.chaos, smooth);
            p.pulseMag = lerp(p.pulseMag, target.pulse, smooth);
            p.radiusScale = lerp(p.radiusScale, target.radius, smooth);
            p.swirl = lerp(p.swirl, target.swirl, smooth);

            // 3. Physics
            const time = Date.now() / 1000;
            // Complex organic pulse: Main beat + secondary flutter
            const beat = Math.sin(time * 3) * 0.5 + Math.sin(time * 1.5);
            const pulseFactor = 1.0 + (beat * 0.15 * p.pulseMag);

            ctx.fillStyle = '#000000';

            particles.forEach((pt) => {
                const dx = centerX - pt.x;
                const dy = centerY - pt.y;
                const distToCenter = Math.sqrt(dx * dx + dy * dy);

                // FORCE 1: Cohesion (Pull to Center)
                pt.vx += dx * p.cohesion;
                pt.vy += dy * p.cohesion;

                // FORCE 2: Separation (Push away from center if too close)
                // Used for "Thinking" expansion
                if (p.separation > 0 && distToCenter < 100) {
                    pt.vx -= dx * 0.05 * p.separation;
                    pt.vy -= dy * 0.05 * p.separation;
                }

                // FORCE 3: Swirl (Orbital)
                if (p.swirl > 0) {
                    pt.vx += -dy * p.swirl;
                    pt.vy += dx * p.swirl;
                }

                // FORCE 4: Organic Wander (Perlin Noise-ish)
                // Use sin/cos with different frequencies per particle
                pt.vx += Math.sin(time * 0.5 + pt.offset) * 0.2;
                pt.vy += Math.cos(time * 0.3 + pt.offset) * 0.2;

                // FORCE 5: Chaos (Jitter)
                if (p.chaos > 0) {
                    pt.vx += (Math.random() - 0.5) * p.chaos;
                    pt.vy += (Math.random() - 0.5) * p.chaos;
                }

                // Integration & Damping
                pt.vx *= 0.90; // Strong drag
                pt.vy *= 0.90;

                pt.x += pt.vx * p.speedMult;
                pt.y += pt.vy * p.speedMult;

                // Hard Bounds
                const bound = 30; // inset
                if (pt.x < bound) { pt.x = bound; pt.vx *= -0.5; }
                if (pt.x > width - bound) { pt.x = width - bound; pt.vx *= -0.5; }
                if (pt.y < bound) { pt.y = bound; pt.vy *= -0.5; }
                if (pt.y > height - bound) { pt.y = height - bound; pt.vy *= -0.5; }

                // Render
                ctx.beginPath();
                // Individual breathing
                const breathe = 1 + Math.sin(time + pt.offset) * 0.08;
                const r = Math.max(0, pt.baseRadius * p.radiusScale * pulseFactor * breathe);

                ctx.arc(pt.x, pt.y, r, 0, Math.PI * 2);
                ctx.fill();
            });

            animationFrameId = requestAnimationFrame(render);
        };

        render();
        return () => cancelAnimationFrame(animationFrameId);
    }, []);

    return (
        <div ref={containerRef} className="w-full h-full relative"
            style={{ filter: 'blur(8px) contrast(15)', background: '#fff' }}>
            <canvas ref={canvasRef} className="w-full h-full" />
        </div>
    );
}

