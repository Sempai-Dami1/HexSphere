import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { expect, test } from "@playwright/test";

interface Recipe {
  format: string;
  version: string;
  object: { name: string; parts: { id: string }[] };
}

interface Package {
  format: string;
  version: string;
  object: { source_recipe_version: string };
  parts: { id: string }[];
  connections: unknown[];
}

const workspaceRoot = resolve(process.cwd(), "..");
const fixturePath = join(workspaceRoot, "tests", "fixtures", "phase5s", "two_simple_blocks.json");

test("Workbench presents recipe source and evaluated Package 1.0 as separate workflow stages", async ({
  page,
}, testInfo) => {
  test.setTimeout(360_000);
  await page.goto("http://127.0.0.1:8503", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Open Object Recipe Workbench" }).click();
  const workbench = page.getByTestId("stExpander").filter({
    has: page.getByText("Object Recipe Workbench — Recipe v0.6", { exact: true }),
  });
  await expect(workbench).toBeVisible({ timeout: 120_000 });

  const uploader = workbench.getByRole("region", { name: "Import Object Recipe v0.6 JSON" });
  await uploader.getByTestId("stFileUploaderDropzoneInput").setInputFiles(fixturePath);
  await expect(uploader.getByRole("button", { name: /Remove two_simple_blocks\.json/ }))
    .toBeVisible({ timeout: 30_000 });
  await workbench.getByRole("button", { name: "Load uploaded recipe" }).click();
  await expect(workbench.getByText("Validated v0.6 recipe JSON loaded.")).toBeVisible();

  for (const heading of [
    "1. Start or author a recipe",
    "Guided authoring",
    "2. Advanced source editing",
    "3. Validate and evaluate",
    "4. Evaluated Package 1.0 and preview",
  ]) {
    await expect(workbench.getByText(heading, { exact: true })).toBeVisible();
  }
  await expect(workbench.getByText(
    "Recipe download: exports the validated source Object Recipe v0.6 JSON.",
    { exact: true },
  )).toBeVisible();
  await expect(workbench.getByText(
    "This package is evaluated interchange data, not an editable recipe. The Plotly preview interprets the same validated package that is offered for download.",
    { exact: true },
  )).toHaveCount(0);
  await expect(workbench.getByText("No current evaluated result.", { exact: false })).toBeVisible();
  const packageDownloadControl = workbench.getByText("Export Object Package 1.0", { exact: true });
  await expect(packageDownloadControl).toHaveCount(0);

  const expectedRecipe = JSON.parse(await readFile(fixturePath, "utf8")) as Recipe;
  const recipeDownloadPromise = page.waitForEvent("download");
  await workbench.getByRole("button", { name: "Export Object Recipe v0.6" }).click();
  const recipeDownload = await recipeDownloadPromise;
  const recipePath = testInfo.outputPath(recipeDownload.suggestedFilename());
  await recipeDownload.saveAs(recipePath);
  const downloadedRecipe = JSON.parse(await readFile(recipePath, "utf8")) as Recipe;
  expect(downloadedRecipe).toEqual(expectedRecipe);

  await workbench.getByRole("button", { name: "Validate, evaluate, and preview" }).click();
  await expect(workbench.getByText(
    "Recipe evaluated and exported as Object Package 1.0.",
  )).toBeVisible({ timeout: 60_000 });
  await expect(packageDownloadControl).toBeVisible();

  const packageDownloadPromise = page.waitForEvent("download");
  await packageDownloadControl.click();
  const packageDownload = await packageDownloadPromise;
  const packagePath = testInfo.outputPath(packageDownload.suggestedFilename());
  await packageDownload.saveAs(packagePath);
  const evaluatedPackage = JSON.parse(await readFile(packagePath, "utf8")) as Package;
  expect(evaluatedPackage.format).toBe("hexsphere.object-package");
  expect(evaluatedPackage.version).toBe("1.0");
  expect(evaluatedPackage.object.source_recipe_version).toBe("0.6");
  expect(evaluatedPackage.parts.map((part) => part.id)).toEqual(["base", "upper"]);
  expect(evaluatedPackage.connections).toHaveLength(1);
});
