import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

interface PackagePart {
  id: string;
  type: string;
  geometry: { vertices: number[][]; faces: number[][]; edges: number[][] };
  transform: { position: number[]; rotation: number[][]; scale: number[] };
  anchors: { name: string; position: number[]; rotation: number[][] }[];
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
    source: { name: string; position: number[]; rotation: number[][] };
    target_anchor_frame: { name: string; position: number[]; rotation: number[][] };
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
    anchors: PackagePart["anchors"];
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
}

const workspaceRoot = resolve(process.cwd(), "..");
const referenceScript = join(process.cwd(), "scripts", "phase5p_python_reference.py");
const pythonExecutable = join(workspaceRoot, ".venv", "Scripts", "python.exe");

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

test("real Streamlit Object Package download loads unchanged in Python and Babylon", async ({ page, context }, testInfo) => {
  test.setTimeout(180_000);
  const { actualPackage, downloadPath } = await test.step("Capture actual Streamlit Object Package download", async () => {
    await page.goto("http://127.0.0.1:8503", { waitUntil: "domcontentloaded" });
    const exportLabel = page.getByText("Export Object Package 1.0", { exact: true });
    await expect(exportLabel).toBeVisible({ timeout: 120_000 });
    await expect(page.getByText("Import Object Package", { exact: true })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText("Drop an Object Package JSON file here or browse", { exact: true })).toBeVisible();
    const downloadPromise = page.waitForEvent("download");
    await exportLabel.click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("simplehexshpere.object-package.json");
    const path = testInfo.outputPath(download.suggestedFilename());
    await download.saveAs(path);
    const downloaded = JSON.parse(await readFile(path, "utf8")) as RealPackage;
    expect(downloaded.format).toBe("hexsphere.object-package");
    expect(downloaded.version).toBe("1.0");
    expect(downloaded.object.name).toBe("SimpleHexShpere");
    expect(downloaded.object.source_recipe_version).toBe("0.6");

    const uploaderRegion = page.getByRole("region", { name: /Drop an Object Package JSON/ });
    await uploaderRegion.getByTestId("stFileUploaderDropzoneInput").setInputFiles(path);
    await expect(uploaderRegion.getByRole("button", { name: /Remove simplehexshpere\.object-package\.json/ }))
      .toBeVisible({ timeout: 30_000 });
    await page.getByRole("button", { name: "Import Object Package" }).click();
    await expect(page.getByText("Validated Object Package 1.0: SimpleHexShpere", { exact: true }))
      .toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("Imported Object Package: SimpleHexShpere", { exact: true }))
      .toBeVisible({ timeout: 60_000 });
    return { actualPackage: downloaded, downloadPath: path };
  });

  const reference = await test.step("Validate the same downloaded file with Python consumer and Plotly", async () => {
    const referenceText = execFileSync(pythonExecutable, ["-X", "utf8", referenceScript, downloadPath], {
      cwd: workspaceRoot,
      encoding: "utf8",
      timeout: 60_000,
      maxBuffer: 8 * 1024 * 1024,
    });
    const result = JSON.parse(referenceText) as PythonReference;
    expect(result.name).toBe(actualPackage.object.name);
    expect(result.source_recipe_version).toBe(actualPackage.object.source_recipe_version);
    expect(result.plotly_trace_count).toBe(actualPackage.parts.length);
    expect(result.parts.map((part) => part.id)).toEqual(actualPackage.parts.map((part) => part.id));
    return result;
  });

  const { babylonPage, state } = await test.step("Import same file and inspect Babylon scene", async () => {
    const scenePage = await context.newPage();
    scenePage.on("pageerror", (error) => console.error(`Babylon page error: ${error.message}`));
    await scenePage.goto("http://127.0.0.1:4173", { waitUntil: "domcontentloaded", timeout: 30_000 });
    const canvas = scenePage.locator("#render-canvas");
    await expect(canvas).toBeVisible({ timeout: 15_000 });
    await expect(canvas).toHaveAttribute("data-rendered", "true", { timeout: 15_000 });
    await expect(canvas).toHaveAttribute("data-package-loaded", "true");
    const downloadedBytes = await readFile(downloadPath);
    await scenePage.locator("#package-dropzone").evaluate((element, file) => {
      const bytes = Uint8Array.from(atob(file.base64), (character) => character.charCodeAt(0));
      const transferredFile = new File([bytes], file.name, { type: "application/json" });
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(transferredFile);
      element.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer }));
      element.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer }));
    }, { name: actualPackage.object.name + ".object-package.json", base64: downloadedBytes.toString("base64") });
    await expect(scenePage.locator("#status")).toContainText(`Loaded ${actualPackage.object.name}`);
    await expect(canvas).toHaveAttribute("data-rendered", "true");
    return { babylonPage: scenePage, state: await getBabylonState(scenePage) };
  });

  expect(state.rightHanded).toBe(true);
  expect(state.partIds).toEqual(reference.parts.map((part) => part.id));
  expect(state.parts.map((part) => part.id)).toEqual(reference.parts.map((part) => part.id));
  expect(state.parts).toHaveLength(actualPackage.parts.length);
  expect(reference.plotly_trace_count).toBe(state.parts.length);

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
    expect(packagePart.geometry.faces).toEqual(expected.faces);
    expect(packagePart.geometry.edges).toEqual(expected.edges);
    expect(expected.plotly_trace).toMatchObject({ name: expected.id, type: "mesh3d" });
  }
  expect(vertexCount).toBe(reference.resources.vertices);
  expect(faceCount).toBe(reference.resources.faces);
  expect(edgeCount).toBe(reference.resources.edges);

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