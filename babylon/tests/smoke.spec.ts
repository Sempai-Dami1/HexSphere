import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

interface PackagePartFixture {
  id: string;
  transform: { position: number[]; rotation: number[][]; scale: number[] };
  anchors: { name: string; position: number[] }[];
  geometry: { vertices: number[][]; faces: number[][]; edges: number[][] };
}

interface PackageFixture {
  coordinate_system: Record<string, string>;
  object: { name: string };
  parts: PackagePartFixture[];
  connections: {
    id: string;
    part: string;
    anchor: string;
    target: { part: string; anchor: string };
    source: { position: number[] };
    target_anchor_frame: { position: number[] };
  }[];
}

interface PlotlyPartReference {
  id: string;
  type: string;
  vertices: number[][];
  faces: number[][];
  edges: number[][];
  bounds: number[][];
  transform: PackagePartFixture["transform"];
  anchors: { name: string; position: number[] }[];
}

interface ValidationCase {
  id: string;
  label: string;
  features: string[];
  package: string;
  reference: string;
  counts: { parts: number; connections: number; vertices: number; faces: number; edges: number };
  tolerance: number;
}

interface BabylonPartState {
  id: string;
  positions: number[];
  indices: number[];
  edges: number[][];
  position: number[];
  rotation: number[];
  scaling: number[];
  packageTransform: PackagePartFixture["transform"];
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

const fixtureDirectory = new URL("../public/fixtures/phase5n/", import.meta.url);
const manifest = JSON.parse(readFileSync(new URL("manifest.json", fixtureDirectory), "utf8")) as {
  cases: ValidationCase[];
};

function readFixture<T>(filename: string): T {
  return JSON.parse(readFileSync(new URL(filename, fixtureDirectory), "utf8")) as T;
}

async function stateFor(page: Page): Promise<ViewerState> {
  const state = await page.evaluate(() => {
    const viewer = (window as Window & { __hexSphereDebug?: { getState: () => ViewerState } }).__hexSphereDebug;
    return viewer?.getState() ?? null;
  });
  expect(state).not.toBeNull();
  return state as ViewerState;
}

async function uploadCase(page: Page, validationCase: ValidationCase, packageData: PackageFixture): Promise<void> {
  const source = readFileSync(new URL(validationCase.package, fixtureDirectory));
  await page.locator("#package-input").setInputFiles({
    name: validationCase.package,
    mimeType: "application/json",
    buffer: source,
  });
  await expect(page.locator("#status")).toContainText(`Loaded ${packageData.object.name}`);
  await expect(page.locator("#render-canvas")).toHaveAttribute("data-package-loaded", "true");
}

function expectClose(actual: number[], expected: number[], tolerance = 1e-6): void {
  expect(actual).toHaveLength(expected.length);
  for (let index = 0; index < expected.length; index += 1) {
    expect(Math.abs(actual[index] - expected[index])).toBeLessThanOrEqual(tolerance);
  }
}

for (const validationCase of manifest.cases) {
  test(`Phase 5N ${validationCase.id} matches the Python consumer and Plotly`, async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#status")).toContainText("Loaded Babylon Object Package reference");

  const packageData = readFixture<PackageFixture>(validationCase.package);
  const reference = readFixture<{ source: string; parts: PlotlyPartReference[] }>(validationCase.reference);
  await uploadCase(page, validationCase, packageData);
  const state = await stateFor(page);

  expect(reference.source).toBe("object_package_consumer.build_plotly_figure");
  expect(packageData.coordinate_system.vertex_coordinates).toBe("world-space XYZ");
  expect(state.rightHanded).toBe(true);
  expect(state.partIds).toEqual(packageData.parts.map((part) => part.id));
  expect(state.parts.map((part) => part.id)).toEqual(reference.parts.map((part) => part.id));
  expect(reference.parts).toHaveLength(validationCase.counts.parts);
  expect(packageData.connections).toHaveLength(validationCase.counts.connections);

  let totalVertices = 0;
  let totalFaces = 0;
  let totalEdges = 0;
  for (const [index, expected] of reference.parts.entries()) {
    const actual = state.parts[index];
    const raw = packageData.parts[index];
    totalVertices += expected.vertices.length;
    totalFaces += expected.faces.length;
    totalEdges += expected.edges.length;
    expect(actual.id).toBe(expected.id);
    expect(actual.positions).toHaveLength(expected.vertices.length * 3);
    expectClose(actual.positions, expected.vertices.flat(), validationCase.tolerance);
    expect(actual.indices).toEqual(expected.faces.flat());
    expect(actual.edges).toEqual(expected.edges);
    expectClose(actual.bounds.min, expected.bounds.map(([minimum]) => minimum), validationCase.tolerance);
    expectClose(actual.bounds.max, expected.bounds.map(([, maximum]) => maximum), validationCase.tolerance);
    expectClose(actual.position, [0, 0, 0], validationCase.tolerance);
    expectClose(actual.rotation, [0, 0, 0], validationCase.tolerance);
    expectClose(actual.scaling, [1, 1, 1], validationCase.tolerance);
    expect(actual.packageTransform).toEqual(raw.transform);
  }
  expect(totalVertices).toBe(validationCase.counts.vertices);
  expect(totalFaces).toBe(validationCase.counts.faces);
  expect(totalEdges).toBe(validationCase.counts.edges);

  const expectedAnchors = packageData.parts.flatMap((part) => part.anchors.map((anchor) => ({
    part: part.id,
    name: anchor.name,
    position: anchor.position,
  })));
  expect(state.anchors).toEqual(expectedAnchors);
  expect(state.anchorOverlayCount).toBe(expectedAnchors.length);
  expect(state.connectionOverlayCount).toBe(packageData.connections.length);
  expect(state.connections).toEqual(packageData.connections.map((connection) => ({
    id: connection.id,
    source: connection.source.position,
    target: connection.target_anchor_frame.position,
  })));

  if (validationCase.id === "02-unicode-stack") {
    const extents = reference.parts[0].bounds.map(([minimum, maximum]) => maximum - minimum);
    expect(new Set(extents.map((extent) => extent.toFixed(6))).size).toBeGreaterThan(1);
  }
  });
}

test("rejects malformed coordinate contracts without replacing the loaded package", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const validationCase = manifest.cases[0];
  const packageData = readFixture<PackageFixture>(validationCase.package);
  await uploadCase(page, validationCase, packageData);
  const malformed = structuredClone(packageData);
  malformed.coordinate_system.vertex_coordinates = "local XYZ";
  await page.locator("#package-input").setInputFiles({
    name: "malformed-coordinates.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(malformed)),
  });
  await expect(page.locator("#status")).toContainText("unsupported coordinate contract");
  const state = await stateFor(page);
  expect(state.partIds).toEqual(packageData.parts.map((part) => part.id));
});

test("rejects face indices outside the package vertex array", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const validationCase = manifest.cases[0];
  const packageData = readFixture<PackageFixture>(validationCase.package);
  await uploadCase(page, validationCase, packageData);
  const malformed = structuredClone(packageData);
  malformed.parts[0].geometry.faces[0] = [0, 1, 999_999];
  await page.locator("#package-input").setInputFiles({
    name: "malformed-face.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(malformed)),
  });
  await expect(page.locator("#status")).toContainText("index outside vertex array");
});

test("renders the final ZomBall candidate in WebGL", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const candidate = manifest.cases.find((item) => item.id === "08-zomball-candidate");
  expect(candidate).toBeDefined();
  const packageData = readFixture<PackageFixture>(candidate!.package);
  await uploadCase(page, candidate!, packageData);
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  const visual = await page.locator("#render-canvas").evaluate((element) => {
    const canvas = element as HTMLCanvasElement;
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