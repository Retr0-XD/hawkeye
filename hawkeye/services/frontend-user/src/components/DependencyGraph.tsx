import { useEffect, useRef } from "react";
import type { Graph } from "../api";

// Lightweight SVG dependency graph (no external chart lib to keep the bundle
// small and the free-tier build fast). Renders nodes from graph.edges keys and
// edges from the adjacency lists.
export function DependencyGraph({ graph, loading }: { graph: Graph | null; loading: boolean }) {
  const ref = useRef<SVGSVGElement | null>(null);

  const edges = graph?.edges ?? {};
  const nodes = Object.keys(edges);

  useEffect(() => {
    if (!ref.current || nodes.length === 0) return;
    const svg = ref.current;
    // Use a fixed coordinate space that matches the SVG viewBox so node
    // positions stay aligned regardless of the rendered container width.
    const W = 800;
    const H = 480;
    const cx = W / 2;
    const cy = H / 2;
    const R = Math.min(W, H) / 2 - 60;
    const n = nodes.length;
    const pos = new Map<string, { x: number; y: number }>();
    nodes.forEach((node, i) => {
      const ang = (2 * Math.PI * i) / n - Math.PI / 2;
      pos.set(node, { x: cx + R * Math.cos(ang), y: cy + R * Math.sin(ang) });
    });

    // Clear previous render
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    const ns = "http://www.w3.org/2000/svg";
    // Edges
    edges && Object.entries(edges).forEach(([from, tos]) => {
      const p1 = pos.get(from);
      if (!p1) return;
      (tos ?? []).forEach((to) => {
        const p2 = pos.get(to);
        if (!p2) return;
        const line = document.createElementNS(ns, "line");
        line.setAttribute("x1", String(p1.x));
        line.setAttribute("y1", String(p1.y));
        line.setAttribute("x2", String(p2.x));
        line.setAttribute("y2", String(p2.y));
        line.setAttribute("stroke", "hsl(var(--border))");
        line.setAttribute("stroke-width", "1");
        svg.appendChild(line);
      });
    });
    // Nodes
    nodes.forEach((node) => {
      const p = pos.get(node);
      if (!p) return;
      const g = document.createElementNS(ns, "g");
      const circle = document.createElementNS(ns, "circle");
      circle.setAttribute("cx", String(p.x));
      circle.setAttribute("cy", String(p.y));
      circle.setAttribute("r", "6");
      circle.setAttribute("fill", "hsl(var(--primary))");
      g.appendChild(circle);
      const text = document.createElementNS(ns, "text");
      text.setAttribute("x", String(p.x + 10));
      text.setAttribute("y", String(p.y + 4));
      text.setAttribute("fill", "hsl(var(--foreground))");
      text.setAttribute("font-size", "10");
      text.textContent = node.split("/").pop() ?? node;
      g.appendChild(text);
      svg.appendChild(g);
    });
  }, [graph, nodes]);

  if (loading && !graph) {
    return <div className="h-96 rounded-xl border border-border bg-card animate-pulse" />;
  }

  if (nodes.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
        No dependency graph data yet. The Processing service builds the resource relationship graph from ingestion output.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card p-3">
      <div className="px-1 pb-2 text-sm font-semibold text-foreground">Resource Dependency Graph</div>
      <svg ref={ref} className="w-full" style={{ height: 480 }} viewBox={`0 0 800 480`} />
    </div>
  );
}
