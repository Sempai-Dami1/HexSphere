import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

test("Registry raster-only grid resizing and stack deviations reach the downloaded mesh", async ({ page }, testInfo) => {
  test.setTimeout(180_000);
  await page.goto("http://127.0.0.1:8503", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Open Object Recipe Workbench" }).click();
  const workbench = page.getByTestId("stExpander").filter({
    has: page.getByText("Object Recipe Workbench — Recipe v0.6", { exact: true }),
  });
  await expect(workbench).toBeVisible({ timeout: 120_000 });
  const app = page.getByTestId("stApp");
  await expect(app).toHaveAttribute("data-test-script-state", "notRunning");
  const choose = async (name: string, value: string) => {
    await expect(app).toHaveAttribute("data-test-script-state", "notRunning");
    const choice = workbench.getByRole("combobox", { name, exact: true });
    await choice.scrollIntoViewIfNeeded();
    await choice.click();
    await expect(choice).toHaveAttribute("aria-expanded", "true");
    await page.getByRole("option", { name: value, exact: true }).click();
    await expect(choice).toHaveValue(value);
    await expect(app).toHaveAttribute("data-test-script-state", "notRunning");
  };
  const source = workbench.getByRole("textbox", { name: "Formal Object Recipe v0.6 JSON" });
  // Streamlit briefly retains the old editor and an empty replacement during
  // reruns. Poll all editors until exactly one populated source remains.
  const sources = async () => {
    const values = await source.evaluateAll(nodes => nodes.map(node => (node as HTMLTextAreaElement).value));
    return values.map(value => value ? JSON.parse(value) : null);
  };
  await choose("Registry object type", "Raster profile only");
  await workbench.getByRole("button", { name: "Use raster profile only", exact: true }).click();
  const columns = workbench.getByRole("spinbutton", { name: "Raster grid columns", exact: true });
  const rows = workbench.getByRole("spinbutton", { name: "Raster grid rows", exact: true });
  await expect(columns).toHaveValue("1");
  await expect(rows).toHaveValue("1");
  await expect.poll(sources).toMatchObject([{ object: { profile: { width: 1, height: 1 } } }]);
  const before = await sources();
  await columns.fill("4");
  await rows.fill("3");
  await expect.poll(sources).toEqual(before);
  await workbench.getByRole("button", { name: "Apply grid dimensions", exact: true }).click();
  await expect.poll(async () => (await sources()).map(recipe => recipe?.object.profile ?? null)).toEqual([{
    type: "raster", width: 4, height: 3, data: [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  }]);
  await expect(workbench.getByRole("checkbox", { name: /^Cell [A-C] [A-D]$/ })).toHaveCount(12);
  await choose("Raster stack to edit", "part_1");
  await choose("Raster placement mode", "Start at origin");
  for (const [name, value] of [
    ["Stack layer count", "3"], ["Stack thickness", "4"],
    ["dHorz (X)", "1"], ["dVert (Y)", "2"], ["dScale", "0.1"], ["dAngle", "15"],
  ]) {
    await workbench.getByRole("spinbutton", { name, exact: true }).fill(value);
  }
  await workbench.getByRole("button", { name: "Save raster stack", exact: true }).click();
  await expect.poll(async () => (await sources()).map(recipe => recipe?.object.parts[0].geometry ?? null)).toMatchObject([{
    layer_count: 3, depth: 4, d_horz: 1, d_vert: 2, d_scale: 0.1, d_angle: 15,
    drawing_mode: "Start at origin",
  }]);
  await workbench.getByRole("button", { name: "Validate, evaluate, and preview" }).click();
  const exportButton = workbench.getByRole("button", { name: "Export Object Package 1.0", exact: true });
  await expect(exportButton).toBeVisible({ timeout: 60_000 });
  const pendingDownload = page.waitForEvent("download");
  await exportButton.click();
  const download = await pendingDownload;
  const output = testInfo.outputPath("raster-grid-deviations.object-package.json");
  await download.saveAs(output);
  const exported = JSON.parse(await readFile(output, "utf8"));
  expect(exported.parts).toHaveLength(1);
  expect(exported.parts[0].type).toBe("RasterStack");
  const vertices: number[][] = exported.parts[0].geometry.vertices;
  expect(vertices).toHaveLength(12);
  for (let layer = 0; layer < 3; layer++) {
    const angle = layer * 15 * Math.PI / 180;
    const scale = 1 + layer * 0.1;
    for (const [x, y] of [[0, 2], [0, 3], [1, 2], [1, 3]]) {
      const expected = [
        scale * (Math.cos(angle) * x - Math.sin(angle) * y) + layer,
        scale * (Math.sin(angle) * x + Math.cos(angle) * y) + layer * 2,
        layer * 2,
      ];
      expect(vertices.some(point => point.every((value, axis) => Math.abs(value - expected[axis]) < 1e-8))).toBe(true);
    }
  }
  // Resizing invalidates the old package and preserves the selected controls.
  await columns.fill("2");
  await rows.fill("2");
  await workbench.getByRole("button", { name: "Apply grid dimensions", exact: true }).click();
  await expect(exportButton).toHaveCount(0);
  await expect.poll(async () => (await sources()).map(recipe => recipe?.object.profile ?? null)).toEqual([{
    type: "raster", width: 2, height: 2, data: [1, 0, 0, 0],
  }]);
  await choose("Raster stack to edit", "part_1");
  await expect(workbench.getByRole("spinbutton", { name: "dAngle", exact: true })).toHaveValue(/^15(?:\.0+)?$/);
});
