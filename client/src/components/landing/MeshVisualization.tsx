'use client';

import React, { useEffect, useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, Cpu, Server, Zap, ShieldCheck } from 'lucide-react';

interface MeshNode {
  id: number;
  label: string;
  tier: 'h100' | 'a100' | 'rtx4090' | 'edge';
  x: number;
  y: number;
  vx: number;
  vy: number;
  status: 'ONLINE' | 'ACTIVE' | 'SYNCING';
  vram: string;
  load: number;
  tflops: number;
}

interface PulsePacket {
  id: string;
  fromIndex: number;
  toIndex: number;
}

const TIER_COLORS = {
  h100: {
    base: 'from-amber-400 to-orange-500',
    border: 'border-amber-400/60',
    glow: 'rgba(251, 191, 36, 0.45)',
    tag: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  },
  a100: {
    base: 'from-indigo-500 to-purple-600',
    border: 'border-indigo-400/60',
    glow: 'rgba(129, 140, 248, 0.45)',
    tag: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
  },
  rtx4090: {
    base: 'from-cyan-400 to-blue-600',
    border: 'border-cyan-400/60',
    glow: 'rgba(56, 189, 248, 0.45)',
    tag: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
  },
  edge: {
    base: 'from-emerald-400 to-teal-600',
    border: 'border-emerald-400/60',
    glow: 'rgba(52, 211, 153, 0.45)',
    tag: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  },
};

const INITIAL_NODES: Omit<MeshNode, 'vx' | 'vy' | 'load'>[] = [
  { id: 1, label: 'Node-Alpha (US-East)', tier: 'h100', x: 22, y: 24, status: 'ACTIVE', vram: '80GB HBM3', tflops: 1979 },
  { id: 2, label: 'Node-Omega (Tokyo)', tier: 'h100', x: 74, y: 26, status: 'ACTIVE', vram: '80GB HBM3', tflops: 1979 },
  { id: 3, label: 'Mesh-Core (Frankfurt)', tier: 'a100', x: 48, y: 46, status: 'ACTIVE', vram: '80GB SXM4', tflops: 312 },
  { id: 4, label: 'Rig-7x (Silicon Valley)', tier: 'rtx4090', x: 18, y: 72, status: 'ONLINE', vram: '24GB G6X', tflops: 82.6 },
  { id: 5, label: 'Decentral-09 (Singapore)', tier: 'rtx4090', x: 82, y: 68, status: 'ACTIVE', vram: '24GB G6X', tflops: 82.6 },
  { id: 6, label: 'Nordic-Node (Stockholm)', tier: 'edge', x: 38, y: 78, status: 'ONLINE', vram: '16GB Unified', tflops: 38.4 },
  { id: 7, label: 'Edge-Worker (Sydney)', tier: 'edge', x: 64, y: 80, status: 'SYNCING', vram: '16GB Unified', tflops: 38.4 },
  { id: 8, label: 'Mesh-Gateway (London)', tier: 'a100', x: 32, y: 50, status: 'ACTIVE', vram: '40GB SXM4', tflops: 312 },
];

export function MeshVisualization() {
  const [nodes, setNodes] = useState<MeshNode[]>([]);
  const [selectedNode, setSelectedNode] = useState<MeshNode | null>(null);
  const [packets, setPackets] = useState<PulsePacket[]>([]);
  const [networkSpeed, setNetworkSpeed] = useState('142.8 TFLOP/s');
  const [activeJobs, setActiveJobs] = useState(24);

  useEffect(() => {
    const initialized: MeshNode[] = INITIAL_NODES.map((n) => ({
      ...n,
      vx: (Math.random() - 0.5) * 0.08,
      vy: (Math.random() - 0.5) * 0.08,
      load: Math.floor(Math.random() * 45) + 40,
    }));
    setNodes(initialized);
    setSelectedNode(initialized[2]);

    const animInterval = setInterval(() => {
      setNodes((prev) =>
        prev.map((node) => {
          let nx = node.x + node.vx;
          let ny = node.y + node.vy;
          let nvx = node.vx;
          let nvy = node.vy;

          if (nx < 12 || nx > 88) nvx = -nvx;
          if (ny < 16 || ny > 84) nvy = -nvy;

          return {
            ...node,
            x: Math.max(10, Math.min(90, nx)),
            y: Math.max(14, Math.min(86, ny)),
            vx: nvx,
            vy: nvy,
            load: Math.min(98, Math.max(20, node.load + (Math.random() - 0.5) * 6)),
          };
        })
      );
    }, 80);

    const packetInterval = setInterval(() => {
      setNodes((current) => {
        if (current.length < 2) return current;
        const i1 = Math.floor(Math.random() * current.length);
        let i2 = Math.floor(Math.random() * current.length);
        while (i2 === i1) {
          i2 = Math.floor(Math.random() * current.length);
        }
        setPackets((prev) => [
          ...prev.slice(-6),
          { id: `${Date.now()}-${Math.random()}`, fromIndex: i1, toIndex: i2 },
        ]);
        return current;
      });
      setNetworkSpeed(`${(130 + Math.random() * 30).toFixed(1)} TFLOP/s`);
      setActiveJobs((prev) => Math.max(18, Math.min(42, prev + (Math.random() > 0.5 ? 1 : -1))));
    }, 1800);

    return () => {
      clearInterval(animInterval);
      clearInterval(packetInterval);
    };
  }, []);

  const connections = useMemo(() => {
    const list: { from: MeshNode; to: MeshNode; dist: number; key: string }[] = [];
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 38) {
          list.push({ from: nodes[i], to: nodes[j], dist, key: `${nodes[i].id}-${nodes[j].id}` });
        }
      }
    }
    return list;
  }, [nodes]);

  return (
    <div className="relative w-full h-[520px] md:h-[620px] rounded-2xl overflow-hidden border border-border/60 bg-gradient-to-b from-card/90 via-background/80 to-card/40 backdrop-blur-xl shadow-2xl shadow-blue-500/5">
      {/* Decorative Grid */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:3rem_3rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)]" />

      {/* Top telemetry status bar */}
      <div className="absolute top-4 left-4 right-4 z-20 flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 rounded-xl border border-border/60 bg-background/70 backdrop-blur-md text-xs font-mono">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="font-semibold text-foreground">MESH TOPOLOGY</span>
            <span className="text-muted-foreground">({nodes.length} Nodes Online)</span>
          </div>
          <div className="hidden sm:flex items-center gap-1.5 text-muted-foreground border-l border-border pl-4">
            <Zap className="h-3.5 w-3.5 text-amber-400" />
            <span>Compute:</span>
            <span className="text-foreground font-semibold">{networkSpeed}</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Activity className="h-3.5 w-3.5 text-cyan-400" />
            <span>Deployments:</span>
            <span className="text-foreground font-semibold">{activeJobs} active</span>
          </div>
          <div className="hidden md:flex items-center gap-1 text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
            <ShieldCheck className="h-3 w-3" />
            <span>Decentralized Consensus</span>
          </div>
        </div>
      </div>

      {/* Inter-node connection network */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {connections.map((c) => {
          const isHighlighted =
            selectedNode && (selectedNode.id === c.from.id || selectedNode.id === c.to.id);
          return (
            <g key={c.key}>
              <line
                x1={`${c.from.x}%`}
                y1={`${c.from.y}%`}
                x2={`${c.to.x}%`}
                y2={`${c.to.y}%`}
                stroke={isHighlighted ? '#38bdf8' : 'currentColor'}
                strokeWidth={isHighlighted ? 2 : 1}
                className={isHighlighted ? 'opacity-80' : 'text-border opacity-35'}
                strokeDasharray={isHighlighted ? '4 2' : 'none'}
              />
            </g>
          );
        })}

        {/* Live data packets animating along topology lines */}
        {packets.map((pkt) => {
          const from = nodes[pkt.fromIndex];
          const to = nodes[pkt.toIndex];
          if (!from || !to) return null;

          return (
            <motion.circle
              key={pkt.id}
              r="3"
              fill="#38bdf8"
              filter="url(#glow)"
              initial={{ cx: `${from.x}%`, cy: `${from.y}%`, opacity: 0.9 }}
              animate={{ cx: `${to.x}%`, cy: `${to.y}%`, opacity: [0.9, 1, 0.1] }}
              transition={{ duration: 1.4, ease: 'easeInOut' }}
            />
          );
        })}
      </svg>

      {/* Render interactive nodes */}
      {nodes.map((node) => {
        const themeConfig = TIER_COLORS[node.tier];
        const isSelected = selectedNode?.id === node.id;

        return (
          <motion.div
            key={node.id}
            onClick={() => setSelectedNode(node)}
            className="absolute cursor-pointer -translate-x-1/2 -translate-y-1/2 z-10 group"
            style={{ left: `${node.x}%`, top: `${node.y}%` }}
            whileHover={{ scale: 1.15 }}
            whileTap={{ scale: 0.95 }}
          >
            {/* Outer radar ping ring */}
            <div
              className="absolute -inset-2 rounded-full opacity-60 animate-ping pointer-events-none"
              style={{
                backgroundColor: themeConfig.glow,
                animationDuration: `${3 + (node.id % 3)}s`,
              }}
            />

            {/* Glowing Orb */}
            <div
              className={`relative flex items-center justify-center w-8 h-8 md:w-9 md:h-9 rounded-full bg-gradient-to-br ${themeConfig.base} ${themeConfig.border} border-2 shadow-lg transition-all duration-300 ${
                isSelected ? 'ring-4 ring-blue-500/40 scale-110' : ''
              }`}
              style={{
                boxShadow: `0 0 20px ${themeConfig.glow}`,
              }}
            >
              {node.tier === 'h100' && <Cpu className="w-4 h-4 text-slate-950 font-bold" />}
              {node.tier === 'a100' && <Server className="w-4 h-4 text-white font-bold" />}
              {node.tier === 'rtx4090' && <Zap className="w-4 h-4 text-slate-950 font-bold" />}
              {node.tier === 'edge' && <Activity className="w-4 h-4 text-slate-950 font-bold" />}
            </div>

            {/* Node ID label below */}
            <div className="absolute top-full left-1/2 -translate-x-1/2 mt-1.5 whitespace-nowrap pointer-events-none">
              <div
                className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-medium backdrop-blur-md border ${
                  isSelected ? 'bg-blue-500 text-white border-blue-400' : themeConfig.tag
                }`}
              >
                {node.label.split(' ')[0]}
              </div>
            </div>
          </motion.div>
        );
      })}

      {/* Selected Node Telemetry HUD / Card */}
      <AnimatePresence>
        {selectedNode && (
          <motion.div
            initial={{ opacity: 0, y: 15, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.25 }}
            className="absolute bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-80 z-30 p-4 rounded-xl border border-border/80 bg-card/90 backdrop-blur-xl shadow-xl font-sans"
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                  Node Telemetry
                </span>
                <h4 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                  <Server className="h-4 w-4 text-blue-500" />
                  {selectedNode.label}
                </h4>
              </div>
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                  TIER_COLORS[selectedNode.tier].tag
                }`}
              >
                {selectedNode.tier.toUpperCase()}
              </span>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-border/40">
                <span className="text-muted-foreground">Hardware Spec:</span>
                <span className="font-mono font-semibold text-foreground">{selectedNode.vram}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-border/40">
                <span className="text-muted-foreground">Compute Power:</span>
                <span className="font-mono font-semibold text-foreground">
                  {selectedNode.tflops} TFLOPs
                </span>
              </div>
              <div>
                <div className="flex justify-between text-muted-foreground mb-1">
                  <span>GPU Compute Utilization:</span>
                  <span className="font-mono text-foreground font-semibold">
                    {Math.round(selectedNode.load)}%
                  </span>
                </div>
                <div className="w-full bg-secondary rounded-full h-1.5 overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-blue-500 to-cyan-400"
                    animate={{ width: `${selectedNode.load}%` }}
                    transition={{ duration: 0.4 }}
                  />
                </div>
              </div>
            </div>

            <div className="mt-3 pt-2 border-t border-border/50 flex items-center justify-between text-[11px] text-muted-foreground">
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                Heartbeat: 40ms
              </span>
              <span className="font-mono text-blue-400">P2P Encrypted</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
