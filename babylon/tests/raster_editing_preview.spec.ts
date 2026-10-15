import { expect, test } from "@playwright/test";

test("Editing preview shows unsaved new and existing rasters without saving them", async ({ page }) => {
  test.setTimeout(180_000);
  await page.goto("http://127.0.0.1:8503", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Open Object Recipe Workbench" }).click();
  const workbench = page.getByTestId("stExpander").filter({
    has: page.getByText("Object Recipe Workbench — Recipe v0.6", { exact: true }),
  });
  const app = page.getByTestId("stApp");
  await expect(workbench).toBeVisible({ timeout: 120_000 });
  await expect(app).toHaveAttribute("data-test-script-state", "notRunning");
  const source = workbench.getByRole("textbox", { name: "Formal Object Recipe v0.6 JSON" });
  const sources = async () => {
    const values = await source.evaluateAll(nodes => nodes.map(node => (node as HTMLTextAreaElement).value));
    return values.map(value => value ? JSON.parse(value) : null);
  };
  await expect.poll(sources).toMatchObject([{ object: { parts: [{ id: "part_1", type: "SimpleBlock" }] } }]);
  const before = await sources();
  const toggle = workbench.getByRole("checkbox", { name: "Show raster object being edited", exact: true });
  const graph = workbench.getByTestId("stPlotlyChart").locator(".js-plotly-plot");
  const meshes = async () => graph.evaluateAll(nodes => nodes.flatMap(node => {
    const traces = (node as HTMLElement & { data?: { type: string; name: string; color?: string; opacity?: number; z: number[] }[] }).data ?? [];
    return traces.filter(trace => trace.type === "mesh3d").map(trace => ({
      name: trace.name, color: trace.color, opacity: trace.opacity, depth: Math.max(...trace.z) - Math.min(...trace.z),
    }));
  }));
  await expect(graph).toHaveCount(0);
  await workbench.getByText("Show raster object being edited", { exact: true }).click();
  await expect(toggle).toBeChecked();
  await workbench.getByRole("checkbox", { name: "Cell A A", exact: true }).check({ force: true });
  await expect.poll(meshes).toContainEqual({ name: "stack_1", color: "#f59e0b", opacity: 1, depth: 1 });
  const thickness = workbench.getByRole("spinbutton", { name: "Stack thickness", exact: true });
  await thickness.fill("5");
  await thickness.press("Tab");
  await expect.poll(meshes).toContainEqual({ name: "stack_1", color: "#f59e0b", opacity: 1, depth: 5 });
  await expect.poll(sources).toEqual(before);
  expect((await meshes()).find(mesh => mesh.name === "part_1")?.opacity).toBe(0.15);
  await expect(workbench.getByRole("button", { name: "Export Object Package 1.0", exact: true })).toHaveCount(0);

  // Persist occupancy and create the stack explicitly, then continue editing it.
  await workbench.getByRole("button", { name: "Create raster profile", exact: true }).click();
  await expect.poll(async () => (await sources()).map(recipe => recipe?.object.profile)).toEqual([
    { type: "raster", width: 1, height: 1, data: [1] },
  ]);
  await expect(app).toHaveAttribute("data-test-script-state", "notRunning");
  await expect(thickness).toHaveValue(/^5(?:\.0+)?$/);
  await workbench.getByRole("button", { name: "Create raster stack", exact: true }).click();
  const stackChoice = workbench.getByRole("combobox", { name: "Raster stack to edit", exact: true });
  await expect(stackChoice).toHaveValue("stack_1");
  await expect(app).toHaveAttribute("data-test-script-state", "notRunning");
  await expect.poll(sources).toMatchObject([{ object: { parts: [
    { id: "part_1" }, { id: "stack_1", geometry: { depth: 5 } },
  ] } }]);
  const saved = await sources();
  await thickness.fill("7");
  await thickness.press("Tab");
  await expect.poll(meshes).toContainEqual({ name: "stack_1", color: "#f59e0b", opacity: 1, depth: 7 });
  await expect.poll(async () => (await meshes()).map(mesh => mesh.name).sort()).toEqual(["part_1", "stack_1"]);
  await expect.poll(sources).toEqual(saved);
  await workbench.getByText("Show raster object being edited", { exact: true }).click();
  await expect(toggle).not.toBeChecked();
  await expect(graph).toHaveCount(0);
  await expect.poll(sources).toEqual(saved);
});
