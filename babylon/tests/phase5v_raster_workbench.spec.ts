import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { expect, test } from "@playwright/test";

interface PackagePart {
  id: string;
  type: string;
  geometry: { vertices: number[][]; faces: number[][]; edges: number[][] };
  transform: { position: number[]; rotation: number[][]; scale: number[] };
  anchors: { name: string; position: number[]; rotation: number[][] }[];
}

interface ObjectPackage {
  format: string;
  version: string;
  object: { name: string; source_recipe_version: string };
  coordinate_system: Record<string, string>;
  parts: PackagePart[];
  connections: unknown[];
}

interface Reference {
  name: string;
  source_recipe_version: string;
  coordinate_system: Record<string, string>;
  plotly_trace_count: number;
  resources: { vertices: number; faces: number; edges: number };
  connections: unknown[];
  parts: {
    id: string;
    vertices: number[][];
    faces: number[][];
    edges: number[][];
    transform: PackagePart["transform"];
    anchors: PackagePart["anchors"];
    bounds: number[][];
    plotly_trace: { name: string; type: string; vertices: number; faces: number };
  }[];
}

interface BabylonState {
  rightHanded: boolean;
  partIds: string[];
  connectionMetadata: unknown[];
  parts: {
    id: string;
    positions: number[];
    indices: number[];
    edges: number[][];
    packageTransform: PackagePart["transform"];
    bounds: { min: number[]; max: number[] };
  }[];
}

interface Recipe {
  object: {
    profile: { width: number; height: number; data: number[] };
    parts: { geometry: { depth: number } }[];
  };
}

const workspaceRoot = resolve(process.cwd(), "..");
const fixturePath = join(workspaceRoot, "tests", "fixtures", "phase5v", "raster_stack.json");
const pythonExecutable = join(workspaceRoot, ".venv", "Scripts", "python.exe");
const referenceScript = join(process.cwd(), "scripts", "phase5p_python_reference.py");

test("Native raster edits change topology and depth in real package downloads", async (
  { page, context }, testInfo,
) => {
  test.setTimeout(360_000);
  await page.goto("http://127.0.0.1:8503", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Open Object Recipe Workbench" }).click();
  await expect(page.getByText("Object Recipe Workbench — Recipe v0.6", { exact: true }))
    .toBeVisible({ timeout: 120_000 });
  const uploader = page.getByRole("region", { name: "Import Object Recipe v0.6 JSON" });
  await uploader.getByTestId("stFileUploaderDropzoneInput").setInputFiles(fixturePath);
  await expect(uploader.getByRole("button", { name: /Remove raster_stack\.json/ }))
    .toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Load uploaded recipe" }).click();
  await expect(page.getByText("Validated v0.6 recipe JSON loaded.")).toBeVisible();
  const workbench = page.getByTestId("stExpander").filter({
    has: page.getByText("Object Recipe Workbench — Recipe v0.6", { exact: true }),
  });
  const editor = workbench.getByRole("textbox", { name: "Formal Object Recipe v0.6 JSON" });
  const originalSource = JSON.parse(await readFile(fixturePath, "utf8")) as Recipe;
  async function expectSource(expected: Recipe): Promise<void> {
    await expect.poll(async () => {
      const values = await editor.evaluateAll((nodes) =>
        nodes.map((node) => (node as HTMLTextAreaElement).value));
      return values.map((value) => value === "" ? null : JSON.parse(value));
    }).toEqual([expected]);
    await expect(page.getByTestId("stApp")).toHaveAttribute("data-test-script-state", "notRunning");
  }
  await expectSource(originalSource);
  await expect(workbench.getByRole("spinbutton", { name: "Profile width at creation" })).toHaveCount(0);
  await expect(workbench.getByText("Profile dimensions: 3 columns x 2 rows (fixed).")).toBeVisible();
  const packages: ObjectPackage[] = [];
  const bytes: Buffer[] = [];

  for (const variant of ["base", "depth", "mask"]) {
    const expectedSource = structuredClone(originalSource);
    if (variant !== "base") {
      await page.bringToFront();
      await expect(page.getByTestId("stApp")).toHaveAttribute("data-test-script-state", "notRunning");
      const stackChoice = workbench.getByRole("combobox", { name: "Raster stack to edit", exact: true });
      await stackChoice.scrollIntoViewIfNeeded();
      await stackChoice.click();
      await expect(stackChoice).toHaveAttribute("aria-expanded", "true");
      await page.getByRole("option", { name: "stack", exact: true }).click();
      await expect(workbench.getByText("Stack ID: stack (fixed; rename through explicit JSON only)."))
        .toBeVisible();
      await expect(workbench.getByRole("button", { name: "Create raster stack", exact: true }))
        .toHaveCount(0);
      await expect(page.getByTestId("stApp")).toHaveAttribute("data-test-script-state", "notRunning");
      const depthInput = workbench.getByRole("spinbutton", { name: "Stack depth", exact: true });
      await expect(depthInput).toHaveCount(1);
      await depthInput.fill(variant === "depth" ? "3" : "2");
      await depthInput.press("Tab");
      await expect(depthInput).toHaveValue(variant === "depth" ? /^3(?:\.0+)?$/ : /^2(?:\.0+)?$/);
      await workbench.getByRole("button", { name: "Save raster stack", exact: true }).click();
      if (variant === "depth") expectedSource.object.parts[0].geometry.depth = 3;
      if (variant === "mask") {
        await expectSource(expectedSource);
        await workbench.getByText("Cell row 0 column 1", { exact: true }).click();
        await expect(workbench.getByRole("checkbox", { name: "Cell row 0 column 1", exact: true }))
          .toBeChecked();
        await workbench.getByRole("button", { name: "Save raster occupancy", exact: true }).click();
        expectedSource.object.profile.data[1] = 1;
      }
      await expectSource(expectedSource);
      await expect(workbench.getByRole("button", { name: "Export Object Package 1.0", exact: true }))
        .toHaveCount(0);
    }
    await expectSource(expectedSource);
    await workbench.getByRole("button", { name: "Validate, evaluate, and preview" }).click();
    await expect(workbench.getByText("Recipe evaluated and exported as Object Package 1.0."))
      .toBeVisible({ timeout: 60_000 });
    const resources = variant === "mask"
      ? { vertices: 18, faces: 32, edges: 48 }
      : { vertices: 16, faces: 28, edges: 42 };
    await expect(workbench.getByText(
      `1 part · 0 connections · ${resources.vertices} vertices · ${resources.faces} faces · ${resources.edges} edges`,
    )).toBeVisible();
    await expect(page.getByTestId("stApp")).toHaveAttribute("data-test-script-state", "notRunning");
    const downloadPromise = page.waitForEvent("download");
    await workbench.getByRole("button", { name: "Export Object Package 1.0", exact: true }).click();
    const download = await downloadPromise;
    const packagePath = testInfo.outputPath(`${variant}.object-package.json`);
    await download.saveAs(packagePath);
    const packageBytes = await readFile(packagePath);
    const repeatPromise = page.waitForEvent("download");
    await workbench.getByRole("button", { name: "Export Object Package 1.0", exact: true }).click();
    const repeat = await repeatPromise;
    const repeatPath = testInfo.outputPath(`${variant}-repeat.object-package.json`);
    await repeat.saveAs(repeatPath);
    expect((await readFile(repeatPath)).equals(packageBytes)).toBe(true);
    const actual = JSON.parse(packageBytes.toString("utf8")) as ObjectPackage;
    expect(actual.format).toBe("hexsphere.object-package");
    expect(actual.version).toBe("1.0");
    expect(actual.object.source_recipe_version).toBe("0.6");
    expect(actual.parts.map((part) => part.id)).toEqual(["stack"]);
    expect(actual.parts[0].type).toBe("RasterStack");
    expect(actual.connections).toEqual([]);
    const reference = JSON.parse(execFileSync(
      pythonExecutable, ["-X", "utf8", referenceScript, packagePath],
      { cwd: workspaceRoot, encoding: "utf8", timeout: 60_000, maxBuffer: 8 * 1024 * 1024 },
    )) as Reference;
    expect(reference.name).toBe(actual.object.name);
    expect(reference.source_recipe_version).toBe("0.6");
    expect(reference.coordinate_system).toEqual(actual.coordinate_system);
    expect(reference.resources).toEqual(resources);
    expect(reference.plotly_trace_count).toBe(1);
    expect(reference.connections).toEqual(actual.connections);
    const part = actual.parts[0];
    const expected = reference.parts[0];
    expect(part.geometry.vertices).toEqual(expected.vertices);
    expect(part.geometry.faces).toEqual(expected.faces);
    expect(part.geometry.edges).toEqual(expected.edges);
    expect(part.transform).toEqual(expected.transform);
    expect(part.anchors).toEqual(expected.anchors);
    const depth = variant === "depth" ? 3 : 2;
    expect(Object.fromEntries(part.anchors.map((anchor) => [anchor.name, anchor.position]))).toEqual({
      back: [1, 1, 0], bottom: [1, 0, depth / 2], center: [1, 1, depth / 2],
      front: [1, 1, depth], left: [0, 1, depth / 2], main: [0, 0, 0],
      right: [2, 1, depth / 2], top: [1, 2, depth / 2],
    });
    expect(expected.plotly_trace).toMatchObject({
      name: "stack", type: "mesh3d", vertices: resources.vertices, faces: resources.faces,
    });
    expect(expected.bounds).toEqual([[0, 2], [0, 2], [0, variant === "depth" ? 3 : 2]]);
    expect(part.geometry.vertices).toContainEqual([1, 2, 0]);
    if (variant === "mask") expect(part.geometry.vertices).toContainEqual([2, 2, 0]);
    else expect(part.geometry.vertices).not.toContainEqual([2, 2, 0]);

    const scene = await context.newPage();
    await scene.setViewportSize({ width: 960, height: 640 });
    await scene.goto("http://127.0.0.1:4173", { waitUntil: "domcontentloaded" });
    await scene.locator("#show-anchors").uncheck();
    await scene.locator("#show-connections").uncheck();
    await scene.locator("#package-dropzone").evaluate((element, file) => {
      const contents = Uint8Array.from(atob(file), (character) => character.charCodeAt(0));
      const transfer = new DataTransfer();
      transfer.items.add(new File([contents], "raster.object-package.json", { type: "application/json" }));
      element.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer: transfer }));
      element.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: transfer }));
    }, packageBytes.toString("base64"));
    await expect(scene.locator("#status")).toContainText(`Loaded ${actual.object.name}`);
    await expect(scene.locator("#render-canvas")).toHaveAttribute("data-package-loaded", "true");
    await expect(scene.locator("#render-canvas")).toHaveAttribute("data-rendered", "true");
    await expect(scene.locator("#package-overview")).toContainText("0.6");
    const state = await scene.evaluate(() => {
      const debug = (window as Window & {
        __hexSphereDebug?: { getState: () => BabylonState };
      }).__hexSphereDebug;
      return debug?.getState();
    });
    if (!state) throw new Error("Babylon debug state unavailable after render");
    expect(state.rightHanded).toBe(true);
    expect(state.partIds).toEqual(["stack"]);
    expect(state.connectionMetadata).toEqual([]);
    expect(state.parts[0].positions).toEqual(expected.vertices.flat());
    expect(state.parts[0].indices).toEqual(expected.faces.flat());
    expect(state.parts[0].edges).toEqual(expected.edges);
    expect(state.parts[0].packageTransform).toEqual(expected.transform);
    expect(state.parts[0].bounds.min).toEqual(expected.bounds.map(([minimum]) => minimum));
    expect(state.parts[0].bounds.max).toEqual(expected.bounds.map(([, maximum]) => maximum));
    await scene.locator("#part-select").selectOption("stack");
    await expect(scene.locator("#part-details")).toContainText("RasterStack");
    await scene.close();
    packages.push(actual);
    bytes.push(packageBytes);
  }
  expect(bytes[0].equals(bytes[1])).toBe(false);
  expect(bytes[0].equals(bytes[2])).toBe(false);
  expect(packages[0].parts[0].geometry.faces).toEqual(packages[1].parts[0].geometry.faces);
  expect(packages[0].parts[0].geometry.edges).toEqual(packages[1].parts[0].geometry.edges);
  expect(packages[0].parts[0].geometry.faces).not.toEqual(packages[2].parts[0].geometry.faces);
  for (const actual of packages.slice(1)) {
    expect(actual.parts[0].transform).toEqual(packages[0].parts[0].transform);
  }
  expect(packages[2].parts[0].anchors).toEqual(packages[0].parts[0].anchors);
});
