'use client';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

interface Node {
  id: number;
  x: number;
  y: number;
  active: boolean;
}

export function MeshVisualization() {
  const [nodes, setNodes] = useState<Node[]>([]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;

    // Defer the initial setting of nodes to avoid synchronous setState warning
    const timeout = setTimeout(() => {
        const generatedNodes = Array.from({ length: 15 }).map((_, i) => ({
            id: i,
            x: Math.random() * 100,
            y: Math.random() * 100,
            active: Math.random() > 0.5,
        }));
        setNodes(generatedNodes);

        interval = setInterval(() => {
            setNodes(prev => prev.map(node => ({
                ...node,
                active: Math.random() > 0.7 ? !node.active : node.active
            })));
        }, 2000);
    }, 0);

    return () => {
        clearTimeout(timeout);
        if (interval) clearInterval(interval);
    };
  }, []);

  return (
    <div className="relative w-full h-[400px] md:h-[600px] overflow-hidden rounded-xl border border-border/50 bg-black/50">
      {/* Draw connections */}
      <svg className="absolute inset-0 w-full h-full opacity-30">
        {nodes.map((node, i) =>
          nodes.slice(i + 1).map((targetNode, j) => {
            const distance = Math.sqrt(Math.pow(node.x - targetNode.x, 2) + Math.pow(node.y - targetNode.y, 2));
            if (distance < 40) {
              return (
                <motion.line
                  key={`line-${i}-${j}`}
                  x1={`${node.x}%`}
                  y1={`${node.y}%`}
                  x2={`${targetNode.x}%`}
                  y2={`${targetNode.y}%`}
                  stroke="currentColor"
                  strokeWidth="1"
                  className={node.active && targetNode.active ? "text-blue-500" : "text-gray-700"}
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: 1 }}
                  transition={{ duration: 1.5, ease: "easeInOut" }}
                />
              );
            }
            return null;
          })
        )}
      </svg>

      {/* Draw nodes */}
      {nodes.map((node) => (
        <motion.div
          key={`node-${node.id}`}
          className={`absolute w-3 h-3 rounded-full -ml-1.5 -mt-1.5 ${node.active ? 'bg-blue-500' : 'bg-gray-700'}`}
          style={{ left: `${node.x}%`, top: `${node.y}%` }}
          animate={{
            scale: node.active ? [1, 1.5, 1] : 1,
            boxShadow: node.active ? ['0 0 0 rgba(59, 130, 246, 0)', '0 0 20px rgba(59, 130, 246, 0.8)', '0 0 0 rgba(59, 130, 246, 0)'] : 'none',
          }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
      ))}

      {/* Overlay gradient */}
      <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-transparent" />
    </div>
  );
}
