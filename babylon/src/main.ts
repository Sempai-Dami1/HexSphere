import {
  ArcRotateCamera,
  Color4,
  Engine,
  HemisphericLight,
  Mesh,
  Scene,
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
  parts: DebugPartState[];
  anchorOverlayCount: number;
  connectionOverlayCount: number;
  anchors: { part: string; name: string; position: number[] }[];
  connections: { id: string; source: number[]; target: number[] }[];
}

declare global {
  interface Window {
    __hexSphereDebug?: { getState: () => ViewerDebugState };
  }
}

const canvas = document.querySelector<HTMLCanvasElement>("#render-canvas");
const status = document.querySelector<HTMLElement>("#status");
const packageInput = document.querySelector<HTMLInputElement>("#package-input");
const fixtureButton = document.querySelector<HTMLButtonElement>("#load-fixture");
const partList = document.querySelector<HTMLOListElement>("#part-list");
const spatialList = document.querySelector<HTMLOListElement>("#spatial-list");
const axesToggle = document.querySelector<HTMLInputElement>("#show-axes");
const anchorsToggle = document.querySelector<HTMLInputElement>("#show-anchors");
const connectionsToggle = document.querySelector<HTMLInputElement>("#show-connections");

if (!canvas || !status || !packageInput || !fixtureButton || !partList || !spatialList
  || !axesToggle || !anchorsToggle || !connectionsToggle) {
  throw new Error("The viewer page is missing a required control.");
}

const viewerCanvas = canvas;
const viewerStatus = status;
const viewerPackageInput = packageInput;
const viewerFixtureButton = fixtureButton;
const viewerPartList = partList;
const viewerSpatialList = spatialList;
const viewerAxesToggle = axesToggle;
const viewerAnchorsToggle = anchorsToggle;
const viewerConnectionsToggle = connectionsToggle;

const engine = new Engine(viewerCanvas, true, { preserveDrawingBuffer: true, stencil: true });
const scene = new Scene(engine);
scene.useRightHandedSystem = true;
scene.clearColor = new Color4(0.055, 0.07, 0.085, 1);

const camera = new ArcRotateCamera("viewer-camera", -Math.PI / 3, Math.PI / 3, 8, Vector3.Zero(), scene);
camera.attachControl(canvas, true);
camera.wheelPrecision = 50;
new HemisphericLight("viewer-light", new Vector3(0.25, 1, -0.4), scene);

const axes = createWorldAxes(scene, 2);
let packageData: ObjectPackage | undefined;
let partMeshes: Mesh[] = [];
let anchorMarkers: Mesh[] = [];
let connectionLines: Mesh[] = [];
let connectionMarkers: Mesh[] = [];

function disposeMeshes(meshes: Mesh[]): void {
  for (const mesh of meshes) mesh.dispose(false, true);
}

function showStatus(message: string, error = false): void {
  viewerStatus.textContent = message;
  viewerStatus.dataset.error = String(error);
}

function renderMetadata(value: ObjectPackage): void {
  viewerPartList.replaceChildren();
  viewerSpatialList.replaceChildren();
  for (const part of value.parts) {
    const item = document.createElement("li");
    item.textContent = part.id;
    const detail = document.createElement("span");
    detail.textContent = `${part.type} · ${part.geometry.vertices.length} vertices · ${part.geometry.faces.length} faces`;
    item.append(detail);
    viewerPartList.append(item);
    for (const anchor of part.anchors) {
      const anchorItem = document.createElement("li");
      anchorItem.textContent = `${part.id}.${anchor.name}`;
      const position = document.createElement("span");
      position.textContent = `world ${anchor.position.map((coordinate) => coordinate.toFixed(3)).join(", ")}`;
      anchorItem.append(position);
      viewerSpatialList.append(anchorItem);
    }
  }
  for (const connection of value.connections) {
    const item = document.createElement("li");
    item.textContent = connection.id;
    const detail = document.createElement("span");
    detail.textContent = `${connection.part}.${connection.anchor} → ${connection.target.part}.${connection.target.anchor}`;
    item.append(detail);
    viewerSpatialList.append(item);
  }
}

function debugState(): ViewerDebugState {
  const value = packageData;
  return {
    rightHanded: scene.useRightHandedSystem,
    partIds: value?.parts.map((part) => part.id) ?? [],
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
    connections: value?.connections.map((connection) => ({
      id: connection.id,
      source: connection.source.position,
      target: connection.target_anchor_frame.position,
    })) ?? [],
  };
}

window.__hexSphereDebug = { getState: debugState };

function frameCamera(value: ObjectPackage): void {
  const vertices = value.parts.flatMap((part) => part.geometry.vertices);
  if (vertices.length === 0) return;
  const minimum = [0, 1, 2].map((axis) => Math.min(...vertices.map((point) => point[axis])));
  const maximum = [0, 1, 2].map((axis) => Math.max(...vertices.map((point) => point[axis])));
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
  renderMetadata(parsed);
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

viewerPackageInput.addEventListener("change", async () => {
  const file = viewerPackageInput.files?.[0];
  if (!file) return;
  try {
    loadPackage(JSON.parse(await file.text()));
  } catch (error) {
    showStatus(error instanceof Error ? error.message : "Unable to load the Object Package.", true);
  } finally {
    viewerPackageInput.value = "";
  }
});

viewerFixtureButton.addEventListener("click", () => void loadReferenceFixture());
viewerAxesToggle.addEventListener("change", () => axes.forEach((axis) => axis.setEnabled(viewerAxesToggle.checked)));
viewerAnchorsToggle.addEventListener("change", () => anchorMarkers.forEach((marker) => marker.setEnabled(viewerAnchorsToggle.checked)));
viewerConnectionsToggle.addEventListener("change", () => {
  connectionLines.forEach((line) => line.setEnabled(viewerConnectionsToggle.checked));
  connectionMarkers.forEach((marker) => marker.setEnabled(viewerConnectionsToggle.checked));
});

scene.onAfterRenderObservable.addOnce(() => {
  viewerCanvas.dataset.rendered = "true";
});
engine.runRenderLoop(() => scene.render());
window.addEventListener("resize", () => engine.resize());
void loadReferenceFixture();