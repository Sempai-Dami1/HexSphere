import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

interface Recipe {
  object: {
    profile: { width: number; height: number; data: number[] };
    parts: { id: string; type?: string; geometry?: { type: string } }[];
  };
}

const workbenchTitle = "Object Recipe Workbench — Recipe v0.6";

test("Raster-Only authoring evaluates and exports without registry geometry", async (
  { page }, testInfo,
) => {
  test.setTimeout(180_000);
  await page.goto("http://127.0.0.1:8503", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Open Object Recipe Workbench" }).click();
  const workbench = page.getByTestId("stExpander").filter({
    has: page.getByText(workbenchTitle, { exact: true }),
  });
  await expect(workbench).toBeVisible({ timeout: 120_000 });

  const modeChoice = workbench.getByRole("combobox", { name: "New recipe mode" });
  await modeChoice.focus();
  await modeChoice.press("ArrowDown");
  await modeChoice.press("Enter");
  await expect(modeChoice).toHaveValue("Raster-Only Recipe");
  await workbench.getByRole("spinbutton", { name: "Raster-Only profile width at creation" }).fill("3");
  await workbench.getByRole("spinbutton", { name: "Raster-Only profile height at creation" }).fill("2");
  await workbench.getByRole("button", { name: "Start new guided recipe" }).click();

  const editor = workbench.getByRole("textbox", { name: "Formal Object Recipe v0.6 JSON" });
  await expect.poll(async () => {
    const value = await editor.inputValue();
    return value ? (JSON.parse(value) as Recipe) : null;
  }).toMatchObject({
    object: {
      profile: { width: 3, height: 2, data: [0, 0, 0, 1, 0, 0] },
      parts: [{
        id: "stack_1",
        geometry: { type: "raster_stack" },
      }],
    },
  });
  const recipe = JSON.parse(await editor.inputValue()) as Recipe;
  expect(recipe.object.parts).toHaveLength(1);
  expect(recipe.object.parts[0]).not.toHaveProperty("type");
  await expect(workbench.getByRole("combobox", { name: "Registry object type" })).toHaveCount(0);
  await expect(workbench.getByRole("checkbox", { name: "Cell A A" })).toHaveCount(1);
  await expect(workbench.getByText("Col A", { exact: true })).toBeVisible();
  await expect(workbench.getByText("Row A", { exact: true })).toBeVisible();

  await workbench.getByRole("button", { name: "Validate, evaluate, and preview" }).click();
  await expect(workbench.getByText("Recipe evaluated and exported as Object Package 1.0."))
    .toBeVisible({ timeout: 60_000 });
  const exportButton = workbench.getByRole("button", { name: "Export Object Package 1.0" });
  const downloadPackage = async (name: string): Promise<Buffer> => {
    const promise = page.waitForEvent("download");
    await exportButton.click();
    const download = await promise;
    const path = testInfo.outputPath(name);
    await download.saveAs(path);
    return readFile(path);
  };

  const beforeOverlay = await downloadPackage("raster-only-before.json");
  const packageObject = JSON.parse(beforeOverlay.toString("utf8")) as {
    version: string;
    parts: { type: string }[];
  };
  expect(packageObject.version).toBe("1.0");
  expect(packageObject.parts.map((part) => part.type)).toEqual(["RasterStack"]);

  await workbench.getByText("Show visual anchors", { exact: true }).click();
  const anchorSize = workbench.getByRole("combobox", { name: "Visual anchor cube size" });
  await anchorSize.focus();
  await anchorSize.press("ArrowDown");
  await anchorSize.press("Enter");
  await expect(anchorSize).toHaveValue("4 x 4 x 4");
  const afterOverlay = await downloadPackage("raster-only-after.json");
  expect(afterOverlay.equals(beforeOverlay)).toBe(true);
});
