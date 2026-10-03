import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

interface AnchorFrame {
  name: string;
  position: number[];
  rotation: number[][];
}

interface PackagePart {
  id: string;
  type: string;
  geometry: { vertices: number[][]; faces: number[][]; edges: number[][] };
  transform: { position: number[]; rotation: number[][]; scale: number[] };
  anchors: AnchorFrame[];
}

interface RealPackage {
  format: string;
  version: string;
  object: { name: string; source_recipe_version: string };
  coordinate_system: Record<string, string>;
  parts: PackagePart[];
  connections: {
    id: string;
    part: string;
    anchor: string;
    target: { part: string; anchor: string };
    mode: string;
    offset: number[];
    offset_space: string;
    rotation_offset: number[][];
    source: AnchorFrame;
    target_anchor_frame: AnchorFrame;
  }[];
}

interface PythonReference {
  name: string;
  source_recipe_version: string;
  coordinate_system: Record<string, string>;
  parts: {
    id: string;
    type: string;
    vertices: number[][];
    faces: number[][];
    edges: number[][];
    bounds: number[][];
    transform: PackagePart["transform"];
    anchors: AnchorFrame[];
    plotly_trace: { name: string; type: string; vertices: number; faces: number };
  }[];
  connections: RealPackage["connections"];
  resources: { vertices: number; faces: number; edges: number };
  plotly_trace_count: number;
}

interface BabylonPartState {
  id: string;
  type: string;
  positions: number[];
  indices: number[];
  edges: number[][];
  position: number[];
  rotation: number[];
  scaling: number[];
  packageTransform: PackagePart["transform"];
  bounds: { min: number[]; max: number[] };
}

interface BabylonState {
  rightHanded: boolean;
  partIds: string[];
  parts: BabylonPartState[];
  anchors: { part: string; name: string; position: number[] }[];
  anchorMetadata: { part: string; name: string; position: number[]; rotation: number[][] }[];
  connections: { id: string; source: number[]; target: number[] }[];
  connectionMetadata: RealPackage["connections"];
  anchorOverlayCount: number;
  connectionOverlayCount: number;
}

const workspaceRoot = resolve(process.cwd(), "..");
const referenceScript = join(process.cwd(), "scripts", "phase5p_python_reference.py");
const pythonExecutable = join(workspaceRoot, ".venv", "Scripts", "python.exe");
const expectedPartIds = [
  "platform.deck",
  "post_front_left.member",
  "post_front_right.member",
  "post_back_left.member",
  "post_back_right.member",
  "tie_lower_front.member",
  "tie_lower_back.member",
  "tie_lower_left.member",
  "tie_lower_right.member",
  "tie_upper_front.member",
  "tie_upper_back.member",
  "tie_upper_left.member",
  "tie_upper_right.member",
  "brace_front.member",
  "brace_back.member",
  "brace_left.member",
  "brace_right.member",
  "lookout_post_front_left.member",
  "lookout_post_front_right.member",
  "lookout_post_back_left.member",
  "lookout_post_back_right.member",
  "rail_front.member",
  "rail_back.member",
  "rail_left.member",
  "rail_right.member",
];

function expectClose(actual: number[], expected: number[], tolerance = 1e-6): void {
  expect(actual).toHaveLength(expected.length);
  for (let index = 0; index < expected.length; index += 1) {
    expect(Math.abs(actual[index] - expected[index])).toBeLessThanOrEqual(tolerance);
  }
}

async function getBabylonState(page: Page): Promise<BabylonState> {
  const state = await page.evaluate(() => {
    const debug = (window as Window & { __hexSphereDebug?: { getState: () => BabylonState } }).__hexSphereDebug;
    return debug?.getState() ?? null;
  });
  expect(state).not.toBeNull();
  return state as BabylonState;
}

test("Phase 5R Streamlit download round-trips through Python and Babylon", async ({ page, context }, testInfo) => {
  test.setTimeout(180_000);
  await page.goto("http://127.0.0.1:8503", { waitUntil: "domcontentloaded" });
  const exportButton = page.getByText("Export Phase 5R ZomBall Package 1.0", { exact: true });
  await expect(exportButton).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText("Export Object Package 1.0", { exact: true })).toBeVisible();
  await expect(page.getByText("Import Object Package", { exact: true })).toBeVisible();

  const downloadPath = testInfo.outputPath("zomball_sentry_watch_tower.object-package.json");
  const downloadPromise = page.waitForEvent("download");
  await exportButton.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("zomball_sentry_watch_tower.object-package.json");
  await download.saveAs(downloadPath);
  const downloadedBytes = await readFile(downloadPath);
  const actualPackage = JSON.parse(downloadedBytes.toString("utf8")) as RealPackage;

  expect(actualPackage.format).toBe("hexsphere.object-package");
  expect(actualPackage.version).toBe("1.0");
  expect(actualPackage.object.name).toBe("ZomBall sentry watch tower");
  expect(actualPackage.object.source_recipe_version).toBe("0.6");
  expect(actualPackage.parts.map((part) => part.id)).toEqual(expectedPartIds);
  expect(actualPackage.parts).toHaveLength(25);
  expect(actualPackage.connections).toHaveLength(8);

  const repeatedPath = testInfo.outputPath("zomball_sentry_watch_tower-repeat.object-package.json");
  const repeatedDownloadPromise = page.waitForEvent("download");
  await exportButton.click();
  const repeatedDownload = await repeatedDownloadPromise;
  await repeatedDownload.saveAs(repeatedPath);
  expect(await readFile(repeatedPath)).toEqual(downloadedBytes);

  const referenceText = execFileSync(pythonExecutable, ["-X", "utf8", referenceScript, downloadPath], {
    cwd: workspaceRoot,
    encoding: "utf8",
    timeout: 60_000,
    maxBuffer: 8 * 1024 * 1024,
  });
  const reference = JSON.parse(referenceText) as PythonReference;
  expect(reference.name).toBe(actualPackage.object.name);
  expect(reference.source_recipe_version).toBe(actualPackage.object.source_recipe_version);
  expect(reference.plotly_trace_count).toBe(25);
  expect(reference.parts.map((part) => part.id)).toEqual(expectedPartIds);
  expect(reference.connections).toEqual(actualPackage.connections);
  expect(reference.resources).toEqual({ vertices: 200, faces: 300, edges: 300 });

  for (const [index, expected] of reference.parts.entries()) {
    const part = actualPackage.parts[index];
    expect(part.id).toBe(expected.id);
    expect(part.type).toBe(expected.type);
    expectClose(part.geometry.vertices.flat(), expected.vertices.flat(), 1e-12);
    expect(part.geometry.faces).toEqual(expected.faces);
    expect(part.geometry.edges).toEqual(expected.edges);
    expect(part.transform).toEqual(expected.transform);
    expect(part.anchors).toEqual(expected.anchors);
    expect(expected.plotly_trace).toMatchObject({ name: expected.id, type: "mesh3d" });
  }

  const scenePage = await context.newPage();
  scenePage.on("pageerror", (error) => console.error(`Babylon page error: ${error.message}`));
  await scenePage.setViewportSize({ width: 960, height: 640 });
  await scenePage.goto("http://127.0.0.1:4173", { waitUntil: "domcontentloaded", timeout: 30_000 });
  const canvas = scenePage.locator("#render-canvas");
  await expect(canvas).toBeVisible({ timeout: 15_000 });
  await scenePage.locator("#show-anchors").uncheck();
  await scenePage.locator("#show-connections").uncheck();
  const fileBase64 = downloadedBytes.toString("base64");
  await scenePage.locator("#package-dropzone").evaluate((element, file) => {
    const bytes = Uint8Array.from(atob(file.base64), (character) => character.charCodeAt(0));
    const transferredFile = new File([bytes], file.name, { type: "application/json" });
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(transferredFile);
    element.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer }));
    element.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer }));
  }, { name: actualPackage.object.name + ".object-package.json", base64: fileBase64 });

  await expect(scenePage.locator("#status")).toContainText(`Loaded ${actualPackage.object.name}`);
  await expect(scenePage.locator("#validation-status")).toContainText("Validated hexsphere.object-package v1.0");
  await expect(scenePage.locator("#package-overview")).toContainText(actualPackage.object.name);
  await expect(scenePage.locator("#package-overview")).toContainText("0.6");
  for (const [name, count] of Object.entries({ parts: 25, connections: 8, vertices: 200, faces: 300, edges: 300 })) {
    await expect(scenePage.locator("#resource-summary")).toContainText(name[0].toUpperCase() + name.slice(1));
    await expect(scenePage.locator("#resource-summary")).toContainText(String(count));
  }
  await expect(canvas).toHaveAttribute("data-rendered", "true");
  await expect(canvas).toHaveAttribute("data-package-loaded", "true");

  await scenePage.evaluate(() => new Promise<void>((resolveFrame) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolveFrame()));
  }));
  const visual = await canvas.evaluate((element) => {
    const renderCanvas = element as HTMLCanvasElement;
    const gl = renderCanvas.getContext("webgl2") ?? renderCanvas.getContext("webgl");
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

  const state = await getBabylonState(scenePage);
  expect(state.rightHanded).toBe(true);
  expect(state.partIds).toEqual(expectedPartIds);
  expect(state.parts).toHaveLength(25);
  expect(state.anchorOverlayCount).toBe(actualPackage.parts.reduce((sum, part) => sum + part.anchors.length, 0));
  expect(state.connectionOverlayCount).toBe(8);

  let vertexCount = 0;
  let faceCount = 0;
  let edgeCount = 0;
  for (const [index, expected] of reference.parts.entries()) {
    const actual = state.parts[index];
    const packagePart = actualPackage.parts[index];
    vertexCount += expected.vertices.length;
    faceCount += expected.faces.length;
    edgeCount += expected.edges.length;
    expect(actual.id).toBe(expected.id);
    expect(actual.type).toBe(expected.type);
    expectClose(actual.positions, expected.vertices.flat());
    expect(actual.indices).toEqual(expected.faces.flat());
    expect(actual.edges).toEqual(expected.edges);
    expectClose(actual.bounds.min, expected.bounds.map(([minimum]) => minimum));
    expectClose(actual.bounds.max, expected.bounds.map(([, maximum]) => maximum));
    expectClose(actual.position, [0, 0, 0]);
    expectClose(actual.rotation, [0, 0, 0]);
    expectClose(actual.scaling, [1, 1, 1]);
    expect(actual.packageTransform).toEqual(packagePart.transform);
  }
  expect(vertexCount).toBe(200);
  expect(faceCount).toBe(300);
  expect(edgeCount).toBe(300);

  const expectedAnchors = actualPackage.parts.flatMap((part) => part.anchors.map((anchor) => ({
    part: part.id,
    name: anchor.name,
    position: anchor.position,
  })));
  expect(state.anchors).toEqual(expectedAnchors);
  expect(state.anchorMetadata).toEqual(actualPackage.parts.flatMap((part) => part.anchors.map((anchor) => ({
    part: part.id,
    ...anchor,
  }))));
  expect(state.connections).toEqual(actualPackage.connections.map((connection) => ({
    id: connection.id,
    source: connection.source.position,
    target: connection.target_anchor_frame.position,
  })));
  expect(state.connectionMetadata).toEqual(actualPackage.connections);
});