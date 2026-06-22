import type { NodeHoverDrawingFunction } from "sigma/rendering";

import type { SigmaEdgeAttributes, SigmaNodeAttributes } from "./sigmaGraph";

const GRAPH_LABEL_STYLE = {
  background: "rgba(41, 37, 36, 0.96)",
  border: "#D4AD6A",
  halo: "rgba(212, 173, 106, 0.16)",
  shadow: "rgba(0, 0, 0, 0.32)",
  text: "#F5F5F4",
} as const;
const GRAPH_LABEL_GAP = 7;
const GRAPH_LABEL_MAX_WIDTH = 320;
const GRAPH_LABEL_PADDING_X = 8;
const GRAPH_LABEL_PADDING_Y = 4;
const GRAPH_LABEL_RADIUS = 6;

function ellipsizeLabel(
  context: CanvasRenderingContext2D,
  label: string,
  maxWidth: number,
): string {
  if (context.measureText(label).width <= maxWidth) return label;

  let fittedLabel = label;
  while (
    fittedLabel.length > 1 &&
    context.measureText(`${fittedLabel}...`).width > maxWidth
  ) {
    fittedLabel = fittedLabel.slice(0, -1);
  }

  return `${fittedLabel.trimEnd()}...`;
}

export const drawGraphNodeHover: NodeHoverDrawingFunction<
  SigmaNodeAttributes,
  SigmaEdgeAttributes
> = (context, data, settings) => {
  context.save();

  const haloRadius = data.size + 4;
  context.shadowOffsetX = 0;
  context.shadowOffsetY = 0;
  context.shadowBlur = 12;
  context.shadowColor = GRAPH_LABEL_STYLE.shadow;
  context.fillStyle = GRAPH_LABEL_STYLE.halo;
  context.strokeStyle = GRAPH_LABEL_STYLE.border;
  context.lineWidth = 1.4;
  context.beginPath();
  context.arc(data.x, data.y, haloRadius, 0, Math.PI * 2);
  context.fill();
  context.stroke();

  if (typeof data.label === "string" && data.label.length > 0) {
    const labelSize = settings.labelSize;
    context.font = `${settings.labelWeight} ${labelSize}px ${settings.labelFont}`;
    context.textBaseline = "middle";

    const fittedLabel = ellipsizeLabel(
      context,
      data.label,
      GRAPH_LABEL_MAX_WIDTH,
    );
    const labelWidth = Math.ceil(
      context.measureText(fittedLabel).width + GRAPH_LABEL_PADDING_X * 2,
    );
    const labelHeight = Math.ceil(labelSize + GRAPH_LABEL_PADDING_Y * 2);
    const labelX = data.x + haloRadius + GRAPH_LABEL_GAP;
    const labelY = data.y - labelHeight / 2;

    context.fillStyle = GRAPH_LABEL_STYLE.background;
    context.strokeStyle = GRAPH_LABEL_STYLE.border;
    context.lineWidth = 1;
    context.beginPath();
    context.roundRect(
      labelX,
      labelY,
      labelWidth,
      labelHeight,
      GRAPH_LABEL_RADIUS,
    );
    context.fill();
    context.stroke();

    context.shadowBlur = 0;
    context.fillStyle = GRAPH_LABEL_STYLE.text;
    context.fillText(fittedLabel, labelX + GRAPH_LABEL_PADDING_X, data.y);
  }

  context.restore();
};
