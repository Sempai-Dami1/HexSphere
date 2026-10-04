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
  parts: PackagePart[];
  connections: {
    id: string;
    part: string;
    anchor: string;
    target: { part: string; anchor: string };
    mode: string;
    source: { name: string; position: number[]; rotation: number[][] };
    target_anchor_frame: { name: string; position: number[]; rotation: number[][] };
  }[];
}

interface PythonReference {
  plotly_trace_count: number;
  resources: { vertices: number; faces: number; edges: number };
  parts: { id: string; vertices: number[][]; faces: number[][]; edges: number[][] }[];
}

interface BabylonState {
  partIds: string[];
  parts: { id: string; positions: number[]; indices: number[] }[];
  connectionMetadata: ObjectPackage["connections"];
}

const workspaceRoot = resolve(process.cwd(), "..");
const recipePath = join(workspaceRoot, "tests", "fixtures", "phase5s", "two_simple_blocks.json");
const pythonReferenceScript = join(process.cwd(), "scripts", "phase5p_python_reference.py");
const pythonExecutable = join(workspaceRoot, ".venv", "Scripts", "python.exe");

test("Recipe Workbench downloads a v0.6 recipe and round-trips Package 1.0", async ({ page, context }, testInfo) => {
  test.setTimeout(360_000);
  await page.goto("http://127.0.0.1:8503", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Open Object Recipe Workbench" }).click();
  await expect(page.getByText("Object Recipe Workbench — Recipe v0.6", { exact: true })).toBeVisible({
    timeout: 120_000,
  });

  const recipeUploader = page.getByRole("region", { name: "Import Object Recipe v0.6 JSON" });
  await recipeUploader.getByTestId("stFileUploaderDropzoneInput").setInputFiles(recipePath);
  await expect(recipeUploader.getByRole("button", { name: /Remove two_simple_blocks\.json/ }))
    .toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Load uploaded recipe" }).click();
  await expect(page.getByText("Validated v0.6 recipe JSON loaded.")).toBeVisible();
  const recipeEditor = page.getByRole("textbox", { name: "Formal Object Recipe v0.6 JSON" });
  await expect(recipeEditor).toHaveValue(/Phase 5S Two Block Assembly/);

  const recipeDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export Object Recipe v0.6" }).click();
  const recipeDownload = await recipeDownloadPromise;
  const downloadedRecipePath = testInfo.outputPath(recipeDownload.suggestedFilename());
  await recipeDownload.saveAs(downloadedRecipePath);
  expect(await readFile(downloadedRecipePath)).toEqual(await readFile(recipePath));

  await page.getByRole("spinbutton", { name: "Size" }).fill("3");
  await page.getByRole("button", { name: "Save part and anchor" }).click();
  await expect(recipeEditor).toHaveValue(/"cube_size": 3\.0/, { timeout: 60_000 });

  await page.getByRole("button", { name: "Validate, evaluate, and preview" }).click();
  await expect(page.getByText("Recipe evaluated and exported as Object Package 1.0.")).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByText("2 parts · 1 connection · 16 vertices · 24 faces · 24 edges")).toBeVisible({
    timeout: 60_000,
  });

  const packageDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export Object Package 1.0" }).last().click();
  const packageDownload = await packageDownloadPromise;
  expect(packageDownload.suggestedFilename()).toBe("phase_5s_two_block_assembly.object-package.json");
  const packagePath = testInfo.outputPath(packageDownload.suggestedFilename());
  await packageDownload.saveAs(packagePath);
  const packageBytes = await readFile(packagePath);
  const actualPackage = JSON.parse(packageBytes.toString("utf8")) as ObjectPackage;
  expect(actualPackage.format).toBe("hexsphere.object-package");
  expect(actualPackage.version).toBe("1.0");
  expect(actualPackage.object.source_recipe_version).toBe("0.6");
  expect(actualPackage.parts.map((part) => part.id)).toEqual(["base", "upper"]);
  expect(actualPackage.connections).toHaveLength(1);

  const referenceText = execFileSync(
    pythonExecutable,
    ["-X", "utf8", pythonReferenceScript, packagePath],
    { cwd: workspaceRoot, encoding: "utf8", timeout: 60_000, maxBuffer: 8 * 1024 * 1024 },
  );
  const reference = JSON.parse(referenceText) as PythonReference;
  expect(reference.plotly_trace_count).toBe(2);
  expect(reference.resources).toEqual({ vertices: 16, faces: 24, edges: 24 });
  expect(reference.parts.map((part) => part.id)).toEqual(["base", "upper"]);
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
  const base64 = packageBytes.toString("base64");
  await scenePage.locator("#package-dropzone").evaluate((element, file) => {
    const bytes = Uint8Array.from(atob(file.base64), (character) => character.charCodeAt(0));
    const transferredFile = new File([bytes], file.name, { type: "application/json" });
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(transferredFile);
    element.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer }));
    element.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer }));
  }, { name: packageDownload.suggestedFilename(), base64 });

  await expect(scenePage.locator("#status")).toContainText(`Loaded ${actualPackage.object.name}`);
  await expect(scenePage.locator("#validation-status")).toContainText("Validated hexsphere.object-package v1.0");
  await expect(scenePage.locator("#resource-summary")).toContainText("16");
  await expect(canvas).toHaveAttribute("data-package-loaded", "true");

  const state = await scenePage.evaluate(() => {
    const debug = (window as Window & { __hexSphereDebug?: { getState: () => BabylonState } }).__hexSphereDebug;
    return debug?.getState() ?? null;
  });
  expect(state).not.toBeNull();
  expect((state as BabylonState).partIds).toEqual(["base", "upper"]);
  expect((state as BabylonState).parts).toHaveLength(2);
  expect((state as BabylonState).connectionMetadata).toEqual(actualPackage.connections);
  await scenePage.locator("#part-select").selectOption("upper");
  await expect(scenePage.locator("#part-details")).toContainText("upper");
  await expect(scenePage.locator("#part-details")).toContainText("[0,2,0]");
  await scenePage.close();

  const advancedRecipe = JSON.parse((await readFile(recipePath)).toString("utf8")) as {
    object: { parts: { id: string; anchors: unknown[] }[] };
  };
  advancedRecipe.object.parts[0].anchors.push({
    name: "nested_socket",
    parent: "mount_top",
    local_position: [0, 0.25, 0],
  });
  const advancedText = JSON.stringify(advancedRecipe, null, 2);
  await recipeEditor.fill(advancedText);
  await page.getByRole("button", { name: "Apply JSON edits" }).click();
  await expect(page.getByText("This valid v0.6 recipe contains constructs outside the guided subset.", {
    exact: false,
  })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Recipe evaluated and exported as Object Package 1.0.")).toHaveCount(0);
  const advancedDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export Object Recipe v0.6" }).click();
  const advancedDownload = await advancedDownloadPromise;
  const advancedPath = testInfo.outputPath("advanced.object-recipe.json");
  await advancedDownload.saveAs(advancedPath);
  expect(JSON.parse((await readFile(advancedPath)).toString("utf8"))).toEqual(advancedRecipe);
});
