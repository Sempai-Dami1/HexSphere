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
  object: { replications: { parameters: { size: number } }[] };
}

const workspaceRoot = resolve(process.cwd(), "..");
const fixturePath = join(workspaceRoot, "tests", "fixtures", "phase5u", "component_replication.json");
const pythonExecutable = join(workspaceRoot, ".venv", "Scripts", "python.exe");
const referenceScript = join(process.cwd(), "scripts", "phase5p_python_reference.py");

test("Explicit replication size changes local geometry and both real package downloads", async (
  { page, context }, testInfo,
) => {
  test.setTimeout(360_000);
  await page.goto("http://127.0.0.1:8503", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Open Object Recipe Workbench" }).click();
  await expect(page.getByText("Object Recipe Workbench — Recipe v0.6", { exact: true }))
    .toBeVisible({ timeout: 120_000 });
  const uploader = page.getByRole("region", { name: "Import Object Recipe v0.6 JSON" });
  await uploader.getByTestId("stFileUploaderDropzoneInput").setInputFiles(fixturePath);
  await expect(uploader.getByRole("button", { name: /Remove component_replication\.json/ }))
    .toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Load uploaded recipe" }).click();
  await expect(page.getByText("Validated v0.6 recipe JSON loaded.")).toBeVisible();
  const workbench = page.getByTestId("stExpander").filter({
    has: page.getByText("Object Recipe Workbench — Recipe v0.6", { exact: true }),
  });
  const editor = page.getByRole("textbox", { name: "Formal Object Recipe v0.6 JSON" });
  await expect(editor).toHaveValue(/instance\.parameters\.size/);
  const originalSource = JSON.parse(await editor.inputValue()) as Recipe;
  const packages: ObjectPackage[] = [];
  const bytes: Buffer[] = [];
  const sources: unknown[] = [];

  for (const size of [3, 4]) {
    if (size === 4) {
      await page.getByRole("spinbutton", { name: "Saved replication size", exact: true }).fill("4");
      await page.getByRole("button", { name: "Save replication", exact: true }).click();
      await expect(editor).toHaveValue(/"size": 4\.0/, { timeout: 60_000 });
      const expected = structuredClone(originalSource);
      expected.object.replications[0].parameters.size = 4;
      expect(JSON.parse(await editor.inputValue())).toEqual(expected);
      await expect(workbench.getByRole("button", { name: "Export Object Package 1.0", exact: true }))
        .toHaveCount(0);
    }
    sources.push(JSON.parse(await editor.inputValue()));
    await page.getByRole("button", { name: "Validate, evaluate, and preview" }).click();
    await expect(page.getByText("Recipe evaluated and exported as Object Package 1.0."))
      .toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("2 parts · 0 connections · 16 vertices · 24 faces · 24 edges"))
      .toBeVisible();
    const downloadPromise = page.waitForEvent("download");
    await workbench.getByRole("button", { name: "Export Object Package 1.0", exact: true }).click();
    const download = await downloadPromise;
    const packagePath = testInfo.outputPath(`size-${size}.object-package.json`);
    await download.saveAs(packagePath);
    const packageBytes = await readFile(packagePath);
    const actual = JSON.parse(packageBytes.toString("utf8")) as ObjectPackage;
    expect(actual.format).toBe("hexsphere.object-package");
    expect(actual.version).toBe("1.0");
    expect(actual.object.source_recipe_version).toBe("0.6");
    expect(actual.parts.map((part) => part.id)).toEqual(["row[0].block", "row[1].block"]);
    expect(actual.connections).toEqual([]);
    const reference = JSON.parse(execFileSync(
      pythonExecutable, ["-X", "utf8", referenceScript, packagePath],
      { cwd: workspaceRoot, encoding: "utf8", timeout: 60_000, maxBuffer: 8 * 1024 * 1024 },
    )) as Reference;
    expect(reference.name).toBe(actual.object.name);
    expect(reference.source_recipe_version).toBe("0.6");
    expect(reference.coordinate_system).toEqual(actual.coordinate_system);
    expect(reference.resources).toEqual({ vertices: 16, faces: 24, edges: 24 });
    expect(reference.plotly_trace_count).toBe(2);
    expect(reference.connections).toEqual(actual.connections);
    for (const [index, part] of actual.parts.entries()) {
      const expected = reference.parts[index];
      expect(part.geometry.vertices).toEqual(expected.vertices);
      expect(part.geometry.faces).toEqual(expected.faces);
      expect(part.geometry.edges).toEqual(expected.edges);
      expect(part.transform).toEqual(expected.transform);
      expect(part.anchors).toEqual(expected.anchors);
      expect(expected.plotly_trace).toMatchObject({ name: part.id, type: "mesh3d", vertices: 8, faces: 12 });
      for (let axis = 0; axis < 3; axis++) {
        const coordinates = part.geometry.vertices.map((vertex) => vertex[axis]);
        expect(Math.max(...coordinates) - Math.min(...coordinates)).toBeCloseTo(size, 12);
      }
    }
    const scene = await context.newPage();
    await scene.setViewportSize({ width: 960, height: 640 });
    await scene.goto("http://127.0.0.1:4173", { waitUntil: "domcontentloaded" });
    await scene.locator("#show-anchors").uncheck();
    await scene.locator("#show-connections").uncheck();
    await scene.locator("#package-dropzone").evaluate((element, file) => {
      const contents = Uint8Array.from(atob(file), (character) => character.charCodeAt(0));
      const transfer = new DataTransfer();
      transfer.items.add(new File([contents], "replication.object-package.json", { type: "application/json" }));
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
    expect(state).toBeDefined();
    if (!state) throw new Error("Babylon debug state unavailable after render");
    expect(state.rightHanded).toBe(true);
    expect(state.partIds).toEqual(actual.parts.map((part) => part.id));
    expect(state.connectionMetadata).toEqual(actual.connections);
    for (const [index, part] of state.parts.entries()) {
      const expected = reference.parts[index];
      expect(part.positions).toEqual(expected.vertices.flat());
      expect(part.indices).toEqual(expected.faces.flat());
      expect(part.edges).toEqual(expected.edges);
      expect(part.packageTransform).toEqual(expected.transform);
      expect(part.bounds.min).toEqual(expected.bounds.map(([minimum]) => minimum));
      expect(part.bounds.max).toEqual(expected.bounds.map(([, maximum]) => maximum));
      await scene.locator("#part-select").selectOption(part.id);
      await expect(scene.locator("#part-details")).toContainText(part.id);
    }
    await scene.close();
    packages.push(actual);
    bytes.push(packageBytes);
  }
  expect(bytes[0].equals(bytes[1])).toBe(false);
  expect(sources[0]).toEqual(originalSource);
  for (const [index, part] of packages[0].parts.entries()) {
    expect(part.transform).toEqual(packages[1].parts[index].transform);
    expect(part.geometry.faces).toEqual(packages[1].parts[index].geometry.faces);
    expect(part.geometry.vertices).not.toEqual(packages[1].parts[index].geometry.vertices);
  }
});
