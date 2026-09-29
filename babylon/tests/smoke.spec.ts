import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

interface PlotlyPartReference {
  id: string;
  vertices: number[][];
  faces: number[][];
  bounds: number[][];
}

interface PackageFixture {
  coordinate_system: Record<string, string>;
  parts: {
    id: string;
    transform: { position: number[]; rotation: number[][]; scale: number[] };
    anchors: { name: string; position: number[] }[];
    geometry: { faces: number[][] };
  }[];
  connections: {
    id: string;
    source: { position: number[] };
    target_anchor_frame: { position: number[] };
  }[];
}

interface BabylonPartState {
  id: string;
  positions: number[];
  indices: number[];
  position: number[];
  rotation: number[];
  scaling: number[];
  packageTransform: PackageFixture["parts"][number]["transform"];
  bounds: { min: number[]; max: number[] };
}

interface ViewerState {
  rightHanded: boolean;
  partIds: string[];
  parts: BabylonPartState[];
  anchorOverlayCount: number;
  connectionOverlayCount: number;
  anchors: { part: string; name: string; position: number[] }[];
  connections: { id: string; source: number[]; target: number[] }[];
}

const packageFixture = JSON.parse(readFileSync(new URL("../public/fixtures/object-package-v06.json", import.meta.url), "utf8")) as PackageFixture;
const plotlyReference = JSON.parse(readFileSync(new URL("../public/fixtures/plotly-reference-v06.json", import.meta.url), "utf8")) as {
  source: string;
  parts: PlotlyPartReference[];
};

async function loadedState(page: Page): Promise<ViewerState> {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#status")).toContainText("parts · 1 connections");
  await expect(page.locator("#render-canvas")).toHaveAttribute("data-package-loaded", "true");
  const state = await page.evaluate(() => {
    const viewer = (window as Window & { __hexSphereDebug?: { getState: () => ViewerState } }).__hexSphereDebug;
    return viewer?.getState() ?? null;
  });
  expect(state).not.toBeNull();
  return state as ViewerState;
}

function expectClose(actual: number[], expected: number[], tolerance = 1e-6): void {
  expect(actual).toHaveLength(expected.length);
  for (let index = 0; index < expected.length; index += 1) {
    expect(Math.abs(actual[index] - expected[index])).toBeLessThanOrEqual(tolerance);
  }
}

test("Babylon geometry matches Python consumer and Plotly reference", async ({ page }) => {
  const state = await loadedState(page);

  expect(plotlyReference.source).toBe("object_package_consumer.build_plotly_figure");
  expect(state.rightHanded).toBe(true);
  expect(state.partIds).toEqual(packageFixture.parts.map((part) => part.id));
  expect(state.parts.map((part) => part.id)).toEqual(plotlyReference.parts.map((part) => part.id));
  expect(packageFixture.coordinate_system.vertex_coordinates).toBe("world-space XYZ");

  for (const [index, expected] of plotlyReference.parts.entries()) {
    const actual = state.parts[index];
    const expectedPositions = expected.vertices.flat();
    const expectedIndices = expected.faces.flat();
    expect(actual.id).toBe(expected.id);
    expect(actual.positions).toHaveLength(expectedPositions.length);
    expectClose(actual.positions, expectedPositions);
    expect(actual.indices).toEqual(expectedIndices);
    expectClose(actual.bounds.min, expected.bounds.map((bound) => bound[0]));
    expectClose(actual.bounds.max, expected.bounds.map((bound) => bound[1]));
    expectClose(actual.position, [0, 0, 0]);
    expectClose(actual.rotation, [0, 0, 0]);
    expectClose(actual.scaling, [1, 1, 1]);
  }

  expect(packageFixture.parts.some((part) => part.transform.position.some((value) => value !== 0)
    || part.transform.scale.some((value) => value !== 1))).toBe(true);
  const extents = plotlyReference.parts[1].bounds.map(([minimum, maximum]) => maximum - minimum);
  expect(new Set(extents.map((extent) => extent.toFixed(6))).size).toBeGreaterThan(1);
});

test("evaluated anchors and connections remain world-space metadata", async ({ page }) => {
  const state = await loadedState(page);
  const expectedAnchors = packageFixture.parts.flatMap((part) => part.anchors.map((anchor) => ({
    part: part.id,
    name: anchor.name,
    position: anchor.position,
  })));
  expect(state.anchors).toEqual(expectedAnchors);
  expect(state.anchorOverlayCount).toBe(expectedAnchors.length);
  expect(state.connectionOverlayCount).toBe(packageFixture.connections.length);
  expect(state.connections).toEqual(packageFixture.connections.map((connection) => ({
    id: connection.id,
    source: connection.source.position,
    target: connection.target_anchor_frame.position,
  })));
  await expect(page.locator("#spatial-list")).toContainText("axis_probe.socket");
  await expect(page.locator("#spatial-list")).toContainText("expanded_stack.body.mount");
  await expect(page.locator("#spatial-list")).toContainText("expanded_stack.body.mount → axis_probe.socket");
});

test("rejects malformed coordinate contracts without replacing the loaded package", async ({ page }) => {
  await loadedState(page);
  const malformed = structuredClone(packageFixture);
  malformed.coordinate_system.vertex_coordinates = "local XYZ";
  await page.locator("#package-input").setInputFiles({
    name: "malformed-coordinates.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(malformed)),
  });

  await expect(page.locator("#status")).toContainText("unsupported coordinate contract");
  await expect(page.locator("#render-canvas")).toHaveAttribute("data-package-loaded", "true");
  const state = await page.evaluate(() => (window as Window & { __hexSphereDebug?: { getState: () => ViewerState } })
    .__hexSphereDebug?.getState());
  expect(state?.partIds).toEqual(packageFixture.parts.map((part) => part.id));
});

test("rejects face indices outside the package vertex array", async ({ page }) => {
  await loadedState(page);
  const malformed = structuredClone(packageFixture);
  malformed.parts[0].geometry.faces[0] = [0, 1, 999_999];
  await page.locator("#package-input").setInputFiles({
    name: "malformed-face.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(malformed)),
  });
  await expect(page.locator("#status")).toContainText("index outside vertex array");
});

test("renders non-background pixels in the WebGL canvas", async ({ page }) => {
  await loadedState(page);
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  const visual = await page.locator("#render-canvas").evaluate((canvas) => {
    const gl = canvas.getContext("webgl2") ?? canvas.getContext("webgl");
    if (!gl) return { supported: false, coloredPixels: 0 };
    const pixels = new Uint8Array(gl.drawingBufferWidth * gl.drawingBufferHeight * 4);
    gl.readPixels(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    let coloredPixels = 0;
    for (let offset = 0; offset < pixels.length; offset += 4) {
      if (Math.abs(pixels[offset] - 14) + Math.abs(pixels[offset + 1] - 18) + Math.abs(pixels[offset + 2] - 22) > 28) {
        coloredPixels += 1;
      }
    }
    return { supported: true, coloredPixels };
  });
  expect(visual.supported).toBe(true);
  expect(visual.coloredPixels).toBeGreaterThan(100);
});