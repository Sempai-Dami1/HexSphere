import {
  ArcRotateCamera,
  Color3,
  Color4,
  DynamicTexture,
  Engine,
  HemisphericLight,
  Mesh,
  MeshBuilder,
  Scene,
  StandardMaterial,
  Vector3,
  VertexBuffer,
} from "@babylonjs/core";
import { createPackageOverlays, createPartMeshes, createWorldAxes } from "./babylonAdapter";
import { loadObjectPackageData } from "./objectPackage";
import type { ObjectPackage, PackagePart } from "./objectPackage";
import "./style.css";

interface DebugPartState {
  id: string;
  type: string;
  positions: number[];
  indices: number[];
  edges: [number, number][];
  position: number[];
  rotation: number[];
  scaling: number[];
  packageTransform: PackagePart["transform"];
  bounds: { min: number[]; max: number[] };
}

interface ViewerDebugState {
  rightHanded: boolean;
  partIds: string[];
  selectedPartId: string | null;
  outlinedPartIds: string[];
  partLabelIds: string[];
  parts: DebugPartState[];
  partLabelsEnabled: boolean;
  axesEnabled: boolean;
  anchorsEnabled: boolean;
  connectionsEnabled: boolean;
  camera: { target: number[]; alpha: number; beta: number; radius: number };
  anchorOverlayCount: number;
  connectionOverlayCount: number;
  anchors: { part: string; name: string; position: number[] }[];
  anchorMetadata: { part: string; name: string; position: number[]; rotation: number[][] }[];
  connections: { id: string; source: number[]; target: number[] }[];
  connectionMetadata: ObjectPackage["connections"];
}

declare global {
  interface Window {
    __hexSphereDebug?: { getState: () => ViewerDebugState };
  }
}

const canvas = document.querySelector<HTMLCanvasElement>("#render-canvas");
const status = document.querySelector<HTMLElement>("#status");
const packageInput = document.querySelector<HTMLInputElement>("#package-input");
const importPackageButton = document.querySelector<HTMLButtonElement>("#import-package");
const packageDropzone = document.querySelector<HTMLDivElement>("#package-dropzone");
const fixtureButton = document.querySelector<HTMLButtonElement>("#load-fixture");
const validationStatus = document.querySelector<HTMLElement>("#validation-status");
const packageOverview = document.querySelector<HTMLDListElement>("#package-overview");
const resourceSummary = document.querySelector<HTMLDListElement>("#resource-summary");
const partSelect = document.querySelector<HTMLSelectElement>("#part-select");
const partDetails = document.querySelector<HTMLDListElement>("#part-details");
const partMetadata = document.querySelector<HTMLElement>("#part-metadata");
const anchorSelect = document.querySelector<HTMLSelectElement>("#anchor-select");
const anchorDetails = document.querySelector<HTMLDListElement>("#anchor-details");
const connectionSelect = document.querySelector<HTMLSelectElement>("#connection-select");
const connectionDetails = document.querySelector<HTMLDListElement>("#connection-details");
const axesToggle = document.querySelector<HTMLInputElement>("#show-axes");
const anchorsToggle = document.querySelector<HTMLInputElement>("#show-anchors");
const connectionsToggle = document.querySelector<HTMLInputElement>("#show-connections");
const partLabelsToggle = document.querySelector<HTMLInputElement>("#show-part-labels");
const resetCameraButton = document.querySelector<HTMLButtonElement>("#reset-camera");
const fitObjectButton = document.querySelector<HTMLButtonElement>("#fit-object");

if (!canvas || !status || !packageInput || !importPackageButton || !packageDropzone || !fixtureButton
  || !validationStatus || !packageOverview || !resourceSummary || !partSelect || !partDetails || !partMetadata
  || !anchorSelect || !anchorDetails || !connectionSelect || !connectionDetails || !axesToggle || !anchorsToggle
  || !connectionsToggle || !partLabelsToggle || !resetCameraButton || !fitObjectButton) {
  throw new Error("The viewer page is missing a required control.");
}

const viewerCanvas = canvas;
const viewerStatus = status;
const viewerPackageInput = packageInput;
const viewerImportPackageButton = importPackageButton;
const viewerPackageDropzone = packageDropzone;
const viewerFixtureButton = fixtureButton;
const viewerValidationStatus = validationStatus;
const viewerPackageOverview = packageOverview;
const viewerResourceSummary = resourceSummary;
const viewerPartSelect = partSelect;
const viewerPartDetails = partDetails;
const viewerPartMetadata = partMetadata;
const viewerAnchorSelect = anchorSelect;
const viewerAnchorDetails = anchorDetails;
const viewerConnectionSelect = connectionSelect;
const viewerConnectionDetails = connectionDetails;
const viewerAxesToggle = axesToggle;
const viewerAnchorsToggle = anchorsToggle;
const viewerConnectionsToggle = connectionsToggle;
const viewerPartLabelsToggle = partLabelsToggle;
const viewerResetCameraButton = resetCameraButton;
const viewerFitObjectButton = fitObjectButton;

const engine = new Engine(viewerCanvas, true, { preserveDrawingBuffer: true, stencil: true });
const scene = new Scene(engine);
scene.useRightHandedSystem = true;
scene.clearColor = new Color4(0.055, 0.07, 0.085, 1);

const camera = new ArcRotateCamera("viewer-camera", -Math.PI / 3, Math.PI / 3, 8, Vector3.Zero(), scene);
camera.attachControl(canvas, true);
camera.wheelPrecision = 50;
const initialCamera = { alpha: camera.alpha, beta: camera.beta, radius: camera.radius };
new HemisphericLight("viewer-light", new Vector3(0.25, 1, -0.4), scene);

const axes = createWorldAxes(scene, 2);
let packageData: ObjectPackage | undefined;
let partMeshes: Mesh[] = [];
let anchorMarkers: Mesh[] = [];
let connectionLines: Mesh[] = [];
let connectionMarkers: Mesh[] = [];
let partLabelMeshes: Mesh[] = [];
let selectedPartId: string | null = null;
let selectedAnchorIndex = "";
let selectedConnectionIndex = "";

function disposeMeshes(meshes: Mesh[]): void {
  for (const mesh of meshes) mesh.dispose(false, true);
}

function showStatus(message: string, error = false): void {
  viewerStatus.textContent = message;
  viewerStatus.dataset.error = String(error);
}

function addDetailRows(target: HTMLDListElement, rows: [string, unknown][]): void {
  target.replaceChildren();
  for (const [label, value] of rows) {
    const term = document.createElement("dt");
    term.textContent = label;
    const detail = document.createElement("dd");
    detail.textContent = typeof value === "string" ? value : JSON.stringify(value);
    target.append(term, detail);
  }
}

function partBounds(part: PackagePart): { min: number[]; max: number[] } {
  const minimum = [Infinity, Infinity, Infinity];
  const maximum = [-Infinity, -Infinity, -Infinity];
  for (const vertex of part.geometry.vertices) {
    for (let axis = 0; axis < 3; axis += 1) {
      minimum[axis] = Math.min(minimum[axis], vertex[axis]);
      maximum[axis] = Math.max(maximum[axis], vertex[axis]);
    }
  }
  if (part.geometry.vertices.length === 0) return { min: [0, 0, 0], max: [0, 0, 0] };
  return { min: minimum, max: maximum };
}

function allAnchors(value: ObjectPackage): { partId: string; anchor: PackagePart["anchors"][number] }[] {
  return value.parts.flatMap((part) => part.anchors.map((anchor) => ({ partId: part.id, anchor })));
}

function renderPartDetails(value: ObjectPackage): void {
  const part = value.parts.find((item) => item.id === selectedPartId);
  if (!part) {
    addDetailRows(viewerPartDetails, []);
    viewerPartMetadata.textContent = "";
    return;
  }
  const bounds = partBounds(part);
  addDetailRows(viewerPartDetails, [
    ["ID", part.id],
    ["Type", part.type],
    ["Vertices", part.geometry.vertices.length],
    ["Faces", part.geometry.faces.length],
    ["Edges", part.geometry.edges.length],
    ["Bounds min", bounds.min],
    ["Bounds max", bounds.max],
    ["Transform", part.transform],
  ]);
  viewerPartMetadata.textContent = JSON.stringify(part.metadata, null, 2);
}

function renderAnchorDetails(value: ObjectPackage): void {
  const anchors = allAnchors(value);
  const selected = selectedAnchorIndex === "" ? undefined : anchors[Number(selectedAnchorIndex)];
  addDetailRows(viewerAnchorDetails, selected ? [
    ["Part", selected.partId],
    ["ID", selected.anchor.name],
    ["World position", selected.anchor.position],
    ["Rotation frame", selected.anchor.rotation],
  ] : []);
}

function renderConnectionDetails(value: ObjectPackage): void {
  const selected = selectedConnectionIndex === "" ? undefined : value.connections[Number(selectedConnectionIndex)];
  addDetailRows(viewerConnectionDetails, selected ? [
    ["ID", selected.id],
    ["Source", `${selected.part}.${selected.anchor}`],
    ["Target", `${selected.target.part}.${selected.target.anchor}`],
    ["Mode", selected.mode],
    ["Offset", selected.offset],
    ["Offset space", selected.offset_space],
    ["Rotation offset", selected.rotation_offset],
    ["Source frame", selected.source],
    ["Target frame", selected.target_anchor_frame],
  ] : []);
}

function renderInspector(value: ObjectPackage): void {
  const totalVertices = value.parts.reduce((count, part) => count + part.geometry.vertices.length, 0);
  const totalFaces = value.parts.reduce((count, part) => count + part.geometry.faces.length, 0);
  const totalEdges = value.parts.reduce((count, part) => count + part.geometry.edges.length, 0);
  const anchors = allAnchors(value);
  viewerValidationStatus.textContent = `Validated ${value.format} v${value.version}`;
  addDetailRows(viewerPackageOverview, [
    ["Format", value.format],
    ["Version", value.version],
    ["Object", value.object.name],
    ["Recipe", value.object.source_recipe_version],
    ["Coordinates", value.coordinate_system],
  ]);
  addDetailRows(viewerResourceSummary, [
    ["Parts", value.parts.length],
    ["Vertices", totalVertices],
    ["Faces", totalFaces],
    ["Edges", totalEdges],
    ["Connections", value.connections.length],
    ["Anchors", anchors.length],
  ]);

  viewerPartSelect.replaceChildren();
  for (const part of value.parts) {
    const option = document.createElement("option");
    option.value = part.id;
    option.textContent = part.id;
    viewerPartSelect.append(option);
  }
  if (!value.parts.some((part) => part.id === selectedPartId)) selectedPartId = value.parts[0]?.id ?? null;
  viewerPartSelect.value = selectedPartId ?? "";

  viewerAnchorSelect.replaceChildren();
  anchors.forEach(({ partId, anchor }, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = `${partId}.${anchor.name}`;
    viewerAnchorSelect.append(option);
  });
  if (!anchors[Number(selectedAnchorIndex)]) selectedAnchorIndex = anchors.length > 0 ? "0" : "";
  viewerAnchorSelect.value = selectedAnchorIndex;

  viewerConnectionSelect.replaceChildren();
  value.connections.forEach((connection, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = connection.id;
    viewerConnectionSelect.append(option);
  });
  if (!value.connections[Number(selectedConnectionIndex)]) {
    selectedConnectionIndex = value.connections.length > 0 ? "0" : "";
  }
  viewerConnectionSelect.value = selectedConnectionIndex;
  renderPartDetails(value);
  renderAnchorDetails(value);
  renderConnectionDetails(value);
}

function highlightSelectedPart(): void {
  for (const mesh of partMeshes) {
    const selected = mesh.id === selectedPartId;
    mesh.renderOutline = selected;
    if (selected) {
      mesh.outlineColor = new Color3(0.98, 0.84, 0.34);
      mesh.outlineWidth = 0.035;
    }
  }
}

function setPartLabelsVisible(visible: boolean): void {
  disposeMeshes(partLabelMeshes);
  partLabelMeshes = [];
  if (!visible || !packageData) return;
  for (const part of packageData.parts) {
    const bounds = partBounds(part);
    const center = bounds.min.map((minimum, axis) => (minimum + bounds.max[axis]) / 2);
    const mesh = MeshBuilder.CreatePlane(`part-label-${part.id}`, { width: 1.4, height: 0.35 }, scene);
    const texture = new DynamicTexture(`part-label-texture-${part.id}`, { width: 512, height: 128 }, scene, true);
    texture.hasAlpha = true;
    texture.drawText(part.id, null, 84, "bold 56px Segoe UI", "#f3f7f8", "transparent", true);
    const material = new StandardMaterial(`part-label-material-${part.id}`, scene);
    material.diffuseTexture = texture;
    material.opacityTexture = texture;
    material.emissiveColor = Color3.White();
    material.disableLighting = true;
    material.backFaceCulling = false;
    mesh.material = material;
    mesh.position.set(center[0], bounds.max[1] + 0.25, center[2]);
    mesh.billboardMode = Mesh.BILLBOARDMODE_ALL;
    mesh.isPickable = false;
    mesh.metadata = { partId: part.id };
    partLabelMeshes.push(mesh);
  }
}

function debugState(): ViewerDebugState {
  const value = packageData;
  return {
    rightHanded: scene.useRightHandedSystem,
    partIds: value?.parts.map((part) => part.id) ?? [],
    selectedPartId,
    outlinedPartIds: partMeshes.filter((mesh) => mesh.renderOutline).map((mesh) => mesh.id),
    partLabelIds: partLabelMeshes.map((mesh) => String(mesh.metadata.partId)),
    partLabelsEnabled: viewerPartLabelsToggle.checked,
    axesEnabled: viewerAxesToggle.checked,
    anchorsEnabled: viewerAnchorsToggle.checked,
    connectionsEnabled: viewerConnectionsToggle.checked,
    camera: { target: camera.target.asArray(), alpha: camera.alpha, beta: camera.beta, radius: camera.radius },
    anchorOverlayCount: anchorMarkers.length,
    connectionOverlayCount: connectionMarkers.length,
    parts: partMeshes.map((mesh) => {
      const bounds = mesh.getBoundingInfo().boundingBox;
      return {
        id: mesh.id,
        type: String(mesh.metadata.type),
        positions: Array.from(mesh.getVerticesData(VertexBuffer.PositionKind) ?? []),
        indices: [...(mesh.getIndices() ?? [])],
        edges: mesh.metadata.edges as [number, number][],
        position: mesh.position.asArray(),
        rotation: mesh.rotation.asArray(),
        scaling: mesh.scaling.asArray(),
        packageTransform: mesh.metadata.transform as PackagePart["transform"],
        bounds: { min: bounds.minimum.asArray(), max: bounds.maximum.asArray() },
      };
    }),
    anchors: value?.parts.flatMap((part) => part.anchors.map((anchor) => ({
      part: part.id,
      name: anchor.name,
      position: anchor.position,
    }))) ?? [],
    anchorMetadata: value?.parts.flatMap((part) => part.anchors.map((anchor) => ({
      part: part.id,
      ...anchor,
    }))) ?? [],
    connections: value?.connections.map((connection) => ({
      id: connection.id,
      source: connection.source.position,
      target: connection.target_anchor_frame.position,
    })) ?? [],
    connectionMetadata: value?.connections ?? [],
  };
}

window.__hexSphereDebug = { getState: debugState };

function frameCamera(value: ObjectPackage): void {
  const minimum = [Infinity, Infinity, Infinity];
  const maximum = [-Infinity, -Infinity, -Infinity];
  let vertexCount = 0;
  for (const part of value.parts) {
    for (const point of part.geometry.vertices) {
      vertexCount += 1;
      for (let axis = 0; axis < 3; axis += 1) {
        minimum[axis] = Math.min(minimum[axis], point[axis]);
        maximum[axis] = Math.max(maximum[axis], point[axis]);
      }
    }
  }
  if (vertexCount === 0) return;
  const center = minimum.map((bound, axis) => (bound + maximum[axis]) / 2);
  camera.setTarget(new Vector3(center[0], center[1], center[2]));
  camera.radius = Math.max(...maximum.map((bound, axis) => bound - minimum[axis])) * 2.2 + 1;
}

function loadPackage(value: unknown): void {
  const parsed = loadObjectPackageData(value);
  const meshes = createPartMeshes(scene, parsed);
  const overlays = createPackageOverlays(scene, parsed);
  disposeMeshes([...partMeshes, ...anchorMarkers, ...connectionLines, ...connectionMarkers]);
  packageData = parsed;
  partMeshes = meshes;
  anchorMarkers = overlays.anchorMarkers;
  connectionLines = overlays.connectionLines;
  connectionMarkers = overlays.connectionMarkers;
  axes.forEach((axis) => axis.setEnabled(viewerAxesToggle.checked));
  anchorMarkers.forEach((marker) => marker.setEnabled(viewerAnchorsToggle.checked));
  connectionLines.forEach((line) => line.setEnabled(viewerConnectionsToggle.checked));
  connectionMarkers.forEach((marker) => marker.setEnabled(viewerConnectionsToggle.checked));
  frameCamera(parsed);
  selectedPartId = parsed.parts[0]?.id ?? null;
  selectedAnchorIndex = parsed.parts.some((part) => part.anchors.length > 0) ? "0" : "";
  selectedConnectionIndex = parsed.connections.length > 0 ? "0" : "";
  renderInspector(parsed);
  highlightSelectedPart();
  setPartLabelsVisible(viewerPartLabelsToggle.checked);
  viewerCanvas.dataset.packageLoaded = "true";
  showStatus(`Loaded ${parsed.object.name} · ${parsed.parts.length} parts · ${parsed.connections.length} connections.`);
}

async function loadReferenceFixture(): Promise<void> {
  showStatus("Loading reference fixture...");
  try {
    const response = await fetch("/fixtures/object-package-v06.json");
    if (!response.ok) throw new Error(`Fixture request failed (${response.status}).`);
    loadPackage(await response.json());
  } catch (error) {
    showStatus(error instanceof Error ? error.message : "Unable to load the Object Package.", true);
  }
}

async function importPackageFile(file: File): Promise<void> {
  try {
    loadPackage(JSON.parse(await file.text()));
  } catch (error) {
    showStatus(error instanceof Error ? error.message : "Unable to load the Object Package.", true);
  }
}

viewerImportPackageButton.addEventListener("click", () => viewerPackageInput.click());
viewerPackageInput.addEventListener("change", async () => {
  const file = viewerPackageInput.files?.[0];
  if (file) await importPackageFile(file);
  viewerPackageInput.value = "";
});

viewerPackageDropzone.addEventListener("click", () => viewerPackageInput.click());
viewerPackageDropzone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    viewerPackageInput.click();
  }
});
viewerPackageDropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  viewerPackageDropzone.dataset.dragOver = "true";
});
viewerPackageDropzone.addEventListener("dragleave", (event) => {
  event.preventDefault();
  viewerPackageDropzone.dataset.dragOver = "false";
});
viewerPackageDropzone.addEventListener("drop", async (event) => {
  event.preventDefault();
  viewerPackageDropzone.dataset.dragOver = "false";
  const file = event.dataTransfer?.files[0];
  if (!file) {
    showStatus("Drop one Object Package JSON file.", true);
    return;
  }
  await importPackageFile(file);
});

viewerFixtureButton.addEventListener("click", () => void loadReferenceFixture());
viewerPartSelect.addEventListener("change", () => {
  selectedPartId = viewerPartSelect.value || null;
  if (packageData) renderPartDetails(packageData);
  highlightSelectedPart();
});
viewerAnchorSelect.addEventListener("change", () => {
  selectedAnchorIndex = viewerAnchorSelect.value;
  if (packageData) renderAnchorDetails(packageData);
});
viewerConnectionSelect.addEventListener("change", () => {
  selectedConnectionIndex = viewerConnectionSelect.value;
  if (packageData) renderConnectionDetails(packageData);
});
viewerAxesToggle.addEventListener("change", () => axes.forEach((axis) => axis.setEnabled(viewerAxesToggle.checked)));
viewerAnchorsToggle.addEventListener("change", () => anchorMarkers.forEach((marker) => marker.setEnabled(viewerAnchorsToggle.checked)));
viewerConnectionsToggle.addEventListener("change", () => {
  connectionLines.forEach((line) => line.setEnabled(viewerConnectionsToggle.checked));
  connectionMarkers.forEach((marker) => marker.setEnabled(viewerConnectionsToggle.checked));
});
viewerPartLabelsToggle.addEventListener("change", () => setPartLabelsVisible(viewerPartLabelsToggle.checked));
viewerResetCameraButton.addEventListener("click", () => {
  camera.setTarget(Vector3.Zero());
  camera.alpha = initialCamera.alpha;
  camera.beta = initialCamera.beta;
  camera.radius = initialCamera.radius;
});
viewerFitObjectButton.addEventListener("click", () => {
  if (packageData) frameCamera(packageData);
});

scene.onAfterRenderObservable.addOnce(() => {
  viewerCanvas.dataset.rendered = "true";
});
engine.runRenderLoop(() => scene.render());
window.addEventListener("resize", () => engine.resize());
void loadReferenceFixture();