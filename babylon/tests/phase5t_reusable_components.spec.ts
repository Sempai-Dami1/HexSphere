import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { expect, test } from "@playwright/test";

interface ObjectPackage {
  format: string;
  version: string;
  object: { name: string; source_recipe_version: string };
  parts: {
    id: string;
    geometry: { vertices: number[][]; faces: number[][]; edges: number[][] };
  }[];
  connections: { id: string; part: string; target: { part: string; anchor: string } }[];
}

interface PythonReference {
  plotly_trace_count: number;
  resources: { vertices: number; faces: number; edges: number };
  parts: { id: string; vertices: number[][]; faces: number[][]; edges: number[][] }[];
}

interface BabylonState {
  partIds: string[];
  connectionMetadata: ObjectPackage["connections"];
}

const babylonRoot = process.cwd();
const workspaceRoot = resolve(babylonRoot, "..");
const recipePath = join(workspaceRoot, "tests", "fixtures", "phase5t", "reusable_pair.json");
const pythonReferenceScript = join(babylonRoot, "scripts", "phase5p_python_reference.py");
const pythonExecutable = join(workspaceRoot, ".venv", "Scripts", "python.exe");

test("Reusable components share definitions and export the evaluated assembly", async ({ page, context }, testInfo) => {
  test.setTimeout(360_000);
  await page.goto("http://127.0.0.1:8503", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Open Object Recipe Workbench" }).click();
  await expect(page.getByText("Object Recipe Workbench — Recipe v0.6", { exact: true })).toBeVisible({
    timeout: 120_000,
  });

  const uploader = page.getByRole("region", { name: "Import Object Recipe v0.6 JSON" });
  await uploader.getByTestId("stFileUploaderDropzoneInput").setInputFiles(recipePath);
  await expect(uploader.getByRole("button", { name: /Remove reusable_pair\.json/ })).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("button", { name: "Load uploaded recipe" }).click();
  await expect(page.getByText("Validated v0.6 recipe JSON loaded.")).toBeVisible();

  const recipeEditor = page.getByRole("textbox", { name: "Formal Object Recipe v0.6 JSON" }).last();
  await expect(recipeEditor).toHaveValue(/"component": "Pair"/);

  const componentDefault = page.getByRole("spinbutton", { name: "Default size" });
  await componentDefault.fill("1.5");
  await expect(componentDefault).toHaveValue("1.5");
  await page.getByRole("button", { name: "Save component definition" }).click();
  await expect(recipeEditor).toHaveValue(/"size": 1\.5/, { timeout: 60_000 });

  await page.getByRole("spinbutton", { name: "Instance size" }).fill("2.5");
  await page.getByRole("button", { name: "Save component instance" }).click();
  await expect(recipeEditor).toHaveValue(/"size": 2\.5/, { timeout: 60_000 });
  await expect(recipeEditor).toHaveValue(/"size": 3\.0/);

  await page.getByRole("button", { name: "Validate, evaluate, and preview" }).click();
  await expect(page.getByText("Recipe evaluated and exported as Object Package 1.0.")).toBeVisible({
    timeout: 60_000,
  });
  await expect(
    page.getByText("5 parts · 3 connections · 40 vertices · 60 faces · 60 edges"),
  ).toBeVisible({ timeout: 60_000 });

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export Object Package 1.0" }).last().click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("phase_5t_reusable_pair.object-package.json");
  const packagePath = testInfo.outputPath(download.suggestedFilename());
  await download.saveAs(packagePath);
  const packageBytes = await readFile(packagePath);
  const actualPackage = JSON.parse(packageBytes.toString("utf8")) as ObjectPackage;
  expect(actualPackage.format).toBe("hexsphere.object-package");
  expect(actualPackage.version).toBe("1.0");
  expect(actualPackage.object.source_recipe_version).toBe("0.6");
  expect(actualPackage.parts.map((part) => part.id)).toEqual([
    "base",
    "first.lower",
    "first.upper",
    "second.lower",
    "second.upper",
  ]);
  expect(actualPackage.connections).toHaveLength(3);
  expect(actualPackage.parts[1].geometry.vertices).not.toEqual(actualPackage.parts[3].geometry.vertices);

  const referenceText = execFileSync(
    pythonExecutable,
    ["-X", "utf8", pythonReferenceScript, packagePath],
    { cwd: workspaceRoot, encoding: "utf8", timeout: 60_000, maxBuffer: 8 * 1024 * 1024 },
  );
  const reference = JSON.parse(referenceText) as PythonReference;
  expect(reference.plotly_trace_count).toBe(5);
  expect(reference.resources).toEqual({ vertices: 40, faces: 60, edges: 60 });
  expect(reference.parts.map((part) => part.id)).toEqual(actualPackage.parts.map((part) => part.id));
  for (const [index, part] of actualPackage.parts.entries()) {
    expect(part.geometry.vertices).toEqual(reference.parts[index].vertices);
    expect(part.geometry.faces).toEqual(reference.parts[index].faces);
    expect(part.geometry.edges).toEqual(reference.parts[index].edges);
  }

  const scenePage = await context.newPage();
  await scenePage.setViewportSize({ width: 960, height: 640 });
  await scenePage.goto("http://127.0.0.1:4173", { waitUntil: "domcontentloaded", timeout: 30_000 });
  const canvas = scenePage.locator("#render-canvas");
  await expect(canvas).toBeVisible({ timeout: 15_000 });
  await scenePage.locator("#package-dropzone").evaluate((element, file) => {
    const bytes = Uint8Array.from(atob(file.base64), (character) => character.charCodeAt(0));
    const transferredFile = new File([bytes], file.name, { type: "application/json" });
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(transferredFile);
    element.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer }));
    element.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer }));
  }, { name: download.suggestedFilename(), base64: packageBytes.toString("base64") });

  await expect(scenePage.locator("#status")).toContainText(`Loaded ${actualPackage.object.name}`);
  await expect(scenePage.locator("#validation-status")).toContainText("Validated hexsphere.object-package v1.0");
  await expect(canvas).toHaveAttribute("data-package-loaded", "true");
  const state = await scenePage.evaluate(() => {
    const debug = (window as Window & { __hexSphereDebug?: { getState: () => BabylonState } }).__hexSphereDebug;
    return debug?.getState() ?? null;
  });
  expect(state).not.toBeNull();
  expect((state as BabylonState).partIds).toEqual(actualPackage.parts.map((part) => part.id));
  expect((state as BabylonState).connectionMetadata).toEqual(actualPackage.connections);
  await scenePage.close();
});
