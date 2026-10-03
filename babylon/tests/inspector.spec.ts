import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

interface FixturePart {
  id: string;
  type: string;
  geometry: { vertices: number[][]; faces: number[][]; edges: number[][] };
  transform: { position: number[]; rotation: number[][]; scale: number[] };
  anchors: { name: string; position: number[]; rotation: number[][] }[];
  metadata: Record<string, unknown>;
}

interface FixturePackage {
  format: string;
  version: string;
  object: { name: string; source_recipe_version: string };
  coordinate_system: Record<string, string>;
  parts: FixturePart[];
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

interface InspectorPartState {
  id: string;
  positions: number[];
  indices: number[];
  edges: number[][];
}

interface InspectorState {
  rightHanded: boolean;
  partIds: string[];
  selectedPartId: string | null;
  outlinedPartIds: string[];
  partLabelIds: string[];
  parts: InspectorPartState[];
  partLabelsEnabled: boolean;
  axesEnabled: boolean;
  anchorsEnabled: boolean;
  connectionsEnabled: boolean;
  camera: { target: number[]; alpha: number; beta: number; radius: number };
  anchorMetadata: { part: string; name: string; position: number[]; rotation: number[][] }[];
  connectionMetadata: FixturePackage["connections"];
}

const fixture = JSON.parse(readFileSync(
  new URL("../public/fixtures/object-package-v06.json", import.meta.url),
  "utf8",
)) as FixturePackage;

async function inspectorState(page: import("@playwright/test").Page): Promise<InspectorState> {
  const state = await page.evaluate(() => {
    const inspector = (window as Window & { __hexSphereDebug?: { getState: () => InspectorState } }).__hexSphereDebug;
    return inspector?.getState() ?? null;
  });
  expect(state).not.toBeNull();
  return state as InspectorState;
}

async function activateWithKeyboard(
  page: import("@playwright/test").Page,
  selector: string,
  key: "Enter" | "Space",
): Promise<void> {
  await page.locator(selector).press(key);
  await page.evaluate(() => new Promise<void>((resolveFrame) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolveFrame()));
  }));
}

test("inspector reads Package 1.0 and selection preserves mesh geometry", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#validation-status")).toContainText("Validated hexsphere.object-package v1.0");
  await expect(page.locator("#render-canvas")).toHaveAttribute("data-rendered", "true", { timeout: 15_000 });

  expect(fixture.format).toBe("hexsphere.object-package");
  expect(fixture.version).toBe("1.0");
  expect(fixture.parts.length).toBeGreaterThan(1);
  expect(fixture.connections.length).toBeGreaterThan(0);
  expect(fixture.parts.some((part) => part.anchors.length > 0)).toBe(true);

  await expect(page.locator("#package-overview")).toContainText(fixture.object.name);
  await expect(page.locator("#package-overview")).toContainText(fixture.object.source_recipe_version);
  await expect(page.locator("#package-overview")).toContainText(fixture.coordinate_system.vertex_coordinates);

  const counts = {
    parts: fixture.parts.length,
    vertices: fixture.parts.reduce((sum, part) => sum + part.geometry.vertices.length, 0),
    faces: fixture.parts.reduce((sum, part) => sum + part.geometry.faces.length, 0),
    edges: fixture.parts.reduce((sum, part) => sum + part.geometry.edges.length, 0),
    connections: fixture.connections.length,
    anchors: fixture.parts.reduce((sum, part) => sum + part.anchors.length, 0),
  };
  for (const [name, count] of Object.entries(counts)) {
    await expect(page.locator("#resource-summary")).toContainText(name[0].toUpperCase() + name.slice(1));
    await expect(page.locator("#resource-summary")).toContainText(String(count));
  }

  const initialState = await inspectorState(page);
  expect(initialState.partIds).toEqual(fixture.parts.map((part) => part.id));
  expect(initialState.parts).toHaveLength(fixture.parts.length);
  expect(initialState.anchorMetadata).toEqual(fixture.parts.flatMap((part) => part.anchors.map((anchor) => ({
    part: part.id,
    ...anchor,
  }))));
  expect(initialState.connectionMetadata).toEqual(fixture.connections);

  await page.evaluate(async () => {
    for (const id of ["show-axes", "show-anchors", "show-connections", "show-part-labels"]) {
      const control = document.getElementById(id);
      if (!(control instanceof HTMLInputElement)) {
        throw new Error(`Inspector control #${id} is missing.`);
      }
      control.click();
      await new Promise<void>((resolveFrame) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolveFrame()));
      });
    }
  });
  const toggledState = await inspectorState(page);
  expect(toggledState.axesEnabled).toBe(false);
  expect(toggledState.anchorsEnabled).toBe(false);
  expect(toggledState.connectionsEnabled).toBe(false);
  expect(toggledState.partLabelsEnabled).toBe(true);
  expect(toggledState.partLabelIds).toEqual(fixture.parts.map((part) => part.id));

  const selectedFixturePart = fixture.parts[1];
  const selectedBefore = initialState.parts.find((part) => part.id === selectedFixturePart.id);
  expect(selectedBefore).toBeDefined();
  await page.locator("#part-select").selectOption(selectedFixturePart.id);
  await expect(page.locator("#part-details")).toContainText(selectedFixturePart.id);
  await expect(page.locator("#part-details")).toContainText(selectedFixturePart.type);
  await expect(page.locator("#part-details")).toContainText(JSON.stringify(selectedFixturePart.transform));
  const selectedAfter = await inspectorState(page);
  const selectedMeshAfter = selectedAfter.parts.find((part) => part.id === selectedFixturePart.id);
  expect(selectedAfter.selectedPartId).toBe(selectedFixturePart.id);
  expect(selectedAfter.outlinedPartIds).toEqual([selectedFixturePart.id]);
  expect(selectedMeshAfter?.positions).toEqual(selectedBefore?.positions);
  expect(selectedMeshAfter?.indices).toEqual(selectedBefore?.indices);

  const fixtureAnchors = fixture.parts.flatMap((part) => part.anchors.map((item) => ({ part: part.id, ...item })));
  const anchorIndex = 0;
  const anchor = fixtureAnchors[anchorIndex];
  await page.locator("#anchor-select").selectOption(String(anchorIndex));
  await expect(page.locator("#anchor-details")).toContainText(anchor.part);
  await expect(page.locator("#anchor-details")).toContainText(anchor.name);
  await expect(page.locator("#anchor-details")).toContainText(JSON.stringify(anchor.position));
  await expect(page.locator("#anchor-details")).toContainText(JSON.stringify(anchor.rotation));

  await page.locator("#connection-select").selectOption("0");
  const connection = fixture.connections[0];
  await expect(page.locator("#connection-details")).toContainText(connection.id);
  await expect(page.locator("#connection-details")).toContainText(`${connection.part}.${connection.anchor}`);
  await expect(page.locator("#connection-details")).toContainText(`${connection.target.part}.${connection.target.anchor}`);
  await expect(page.locator("#connection-details")).toContainText(connection.mode);
  await expect(page.locator("#connection-details")).toContainText(JSON.stringify(connection.offset));
  await expect(page.locator("#connection-details")).toContainText(connection.offset_space);

  await activateWithKeyboard(page, "#fit-object", "Enter");
  const fitState = await inspectorState(page);
  expect(fitState.camera.radius).toBeGreaterThan(0);
  await activateWithKeyboard(page, "#reset-camera", "Enter");
  const resetState = await inspectorState(page);
  expect(resetState.camera.target).toEqual([0, 0, 0]);
  expect(resetState.camera.alpha).toBeCloseTo(-Math.PI / 3, 12);
  expect(resetState.camera.beta).toBeCloseTo(Math.PI / 3, 12);
  expect(resetState.camera.radius).toBe(8);
});
