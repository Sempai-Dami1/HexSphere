export const PACKAGE_FORMAT = "hexsphere.object-package";
export const PACKAGE_VERSION = "1.0";

export const COORDINATE_SYSTEM = {
  handedness: "right-handed",
  units: "recipe units",
  vertex_coordinates: "world-space XYZ",
  rotation_representation: "3x3 row-major rotation matrix",
  transform_order: "scale, then rotation, then translation",
  face_winding: "preserved from evaluated mesh generators",
  normal_convention: "not stored; derive from face winding",
  origin: "world origin",
} as const;

export const MAX_VERTICES = 500_000;
export const MAX_FACES = 250_000;
export const MAX_EDGES = 750_000;

export type Vec3 = [number, number, number];
export type Mat3 = [Vec3, Vec3, Vec3];

export interface PackageAnchor {
  name: string;
  position: Vec3;
  rotation: Mat3;
}

export interface PackagePart {
  id: string;
  type: string;
  geometry: {
    vertices: Vec3[];
    faces: [number, number, number][];
    edges: [number, number][];
  };
  transform: {
    position: Vec3;
    rotation: Mat3;
    scale: Vec3;
  };
  anchors: PackageAnchor[];
  metadata: Record<string, unknown>;
}

export interface PackageConnection {
  id: string;
  part: string;
  anchor: string;
  target: { part: string; anchor: string };
  mode: "position" | "snap";
  offset: Vec3;
  offset_space: "target" | "source";
  rotation_offset: Mat3;
  source: PackageAnchor;
  target_anchor_frame: PackageAnchor;
}

export interface ObjectPackage {
  format: typeof PACKAGE_FORMAT;
  version: typeof PACKAGE_VERSION;
  object: { name: string; source_recipe_version: "0.6" };
  coordinate_system: typeof COORDINATE_SYSTEM;
  parts: PackagePart[];
  connections: PackageConnection[];
}

export class ObjectPackageError extends Error {
  constructor(path: string, message: string) {
    super(`Invalid Object Package at ${path}: ${message}`);
    this.name = "ObjectPackageError";
  }
}

function fail(path: string, message: string): never {
  throw new ObjectPackageError(path, message);
}

function record(value: unknown, path: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return fail(path, "expected an object");
  }
  return value as Record<string, unknown>;
}

function exactKeys(value: Record<string, unknown>, keys: string[], path: string): void {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    fail(path, "missing or unsupported fields");
  }
}

function array(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) return fail(path, "expected an array");
  return value;
}

function identifier(value: unknown, path: string): string {
  if (typeof value !== "string" || value.length === 0 || value.length > 512
    || /[\s\u0000-\u001f\u007f]/u.test(value)) {
    return fail(path, "expected a non-empty stable identifier");
  }
  return value;
}

function finiteNumber(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fail(path, "expected a finite number");
  return value;
}

function vector(value: unknown, path: string): Vec3 {
  if (!Array.isArray(value) || value.length !== 3) return fail(path, "expected three numeric values");
  return value.map((item, index) => finiteNumber(item, `${path}[${index}]`)) as Vec3;
}

function rotation(value: unknown, path: string): Mat3 {
  if (!Array.isArray(value) || value.length !== 3) return fail(path, "expected a 3x3 matrix");
  const rows = value.map((row, index) => vector(row, `${path}[${index}]`)) as Mat3;
  for (const row of rows) {
    if (Math.abs(Math.hypot(...row) - 1) > 1e-9) fail(path, "rotation rows must be unit length");
  }
  for (let left = 0; left < 3; left += 1) {
    for (let right = left + 1; right < 3; right += 1) {
      const dot = rows[left][0] * rows[right][0]
        + rows[left][1] * rows[right][1]
        + rows[left][2] * rows[right][2];
      if (Math.abs(dot) > 1e-9) fail(path, "rotation rows must be orthogonal");
    }
  }
  const determinant = rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
    - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
    + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0]);
  if (Math.abs(determinant - 1) > 1e-9) fail(path, "rotation must be right-handed");
  return rows;
}

function anchor(value: unknown, path: string): PackageAnchor {
  const item = record(value, path);
  exactKeys(item, ["name", "position", "rotation"], path);
  return {
    name: identifier(item.name, `${path}.name`),
    position: vector(item.position, `${path}.position`),
    rotation: rotation(item.rotation, `${path}.rotation`),
  };
}

function part(value: unknown, index: number): PackagePart {
  const path = `parts[${index}]`;
  const item = record(value, path);
  exactKeys(item, ["id", "type", "geometry", "transform", "anchors", "metadata"], path);
  const rawGeometry = record(item.geometry, `${path}.geometry`);
  exactKeys(rawGeometry, ["vertices", "faces", "edges"], `${path}.geometry`);
  const rawVertices = array(rawGeometry.vertices, `${path}.geometry.vertices`);
  const rawFaces = array(rawGeometry.faces, `${path}.geometry.faces`);
  const rawEdges = array(rawGeometry.edges, `${path}.geometry.edges`);
  if (rawVertices.length > MAX_VERTICES || rawFaces.length > MAX_FACES || rawEdges.length > MAX_EDGES) {
    fail(`${path}.geometry`, "per-part resource limit exceeded");
  }
  const vertices = rawVertices.map((value, vertexIndex) => vector(value, `${path}.geometry.vertices[${vertexIndex}]`));
  const faces = rawFaces.map((value, faceIndex) => {
    const face = array(value, `${path}.geometry.faces[${faceIndex}]`);
    if (face.length !== 3 || face.some((indexValue) => !Number.isInteger(indexValue))) {
      return fail(`${path}.geometry.faces[${faceIndex}]`, "expected three integer indices");
    }
    if (face.some((indexValue) => (indexValue as number) < 0 || (indexValue as number) >= vertices.length)) {
      return fail(`${path}.geometry.faces[${faceIndex}]`, "index outside vertex array");
    }
    return face as [number, number, number];
  });
  const edges = rawEdges.map((value, edgeIndex) => {
    const edge = array(value, `${path}.geometry.edges[${edgeIndex}]`);
    if (edge.length !== 2 || edge.some((indexValue) => !Number.isInteger(indexValue))) {
      return fail(`${path}.geometry.edges[${edgeIndex}]`, "expected two integer indices");
    }
    if (edge.some((indexValue) => (indexValue as number) < 0 || (indexValue as number) >= vertices.length)) {
      return fail(`${path}.geometry.edges[${edgeIndex}]`, "index outside vertex array");
    }
    return edge as [number, number];
  });
  const transform = record(item.transform, `${path}.transform`);
  exactKeys(transform, ["position", "rotation", "scale"], `${path}.transform`);
  const scale = vector(transform.scale, `${path}.transform.scale`);
  if (scale.some((component) => component === 0)) fail(`${path}.transform.scale`, "scale components cannot be zero");
  const anchors = array(item.anchors, `${path}.anchors`).map((value, anchorIndex) => anchor(value, `${path}.anchors[${anchorIndex}]`));
  if (new Set(anchors.map((item) => item.name)).size !== anchors.length) fail(`${path}.anchors`, "duplicate anchor names");
  const metadata = record(item.metadata, `${path}.metadata`);
  if (typeof item.type !== "string" || item.type.length === 0) fail(`${path}.type`, "expected a non-empty string");
  return {
    id: identifier(item.id, `${path}.id`),
    type: item.type,
    geometry: { vertices, faces, edges },
    transform: {
      position: vector(transform.position, `${path}.transform.position`),
      rotation: rotation(transform.rotation, `${path}.transform.rotation`),
      scale,
    },
    anchors,
    metadata,
  };
}

function connection(value: unknown, index: number): PackageConnection {
  const path = `connections[${index}]`;
  const item = record(value, path);
  exactKeys(item, ["id", "part", "anchor", "target", "mode", "offset", "offset_space", "rotation_offset", "source", "target_anchor_frame"], path);
  const target = record(item.target, `${path}.target`);
  exactKeys(target, ["part", "anchor"], `${path}.target`);
  if (item.mode !== "position" && item.mode !== "snap") fail(`${path}.mode`, "unsupported connection mode");
  if (item.offset_space !== "target" && item.offset_space !== "source") fail(`${path}.offset_space`, "unsupported offset space");
  const source = anchor(item.source, `${path}.source`);
  const targetFrame = anchor(item.target_anchor_frame, `${path}.target_anchor_frame`);
  const anchorName = identifier(item.anchor, `${path}.anchor`);
  const targetAnchorName = identifier(target.anchor, `${path}.target.anchor`);
  if (source.name !== anchorName || targetFrame.name !== targetAnchorName) fail(path, "endpoint frame names do not match references");
  return {
    id: identifier(item.id, `${path}.id`),
    part: identifier(item.part, `${path}.part`),
    anchor: anchorName,
    target: {
      part: identifier(target.part, `${path}.target.part`),
      anchor: targetAnchorName,
    },
    mode: item.mode,
    offset: vector(item.offset, `${path}.offset`),
    offset_space: item.offset_space,
    rotation_offset: rotation(item.rotation_offset, `${path}.rotation_offset`),
    source,
    target_anchor_frame: targetFrame,
  };
}

export function loadObjectPackageData(value: unknown): ObjectPackage {
  const packageData = record(value, "$");
  exactKeys(packageData, ["format", "version", "object", "coordinate_system", "parts", "connections"], "$");
  if (packageData.format !== PACKAGE_FORMAT || packageData.version !== PACKAGE_VERSION) {
    fail("$", "unsupported format or version");
  }
  const objectData = record(packageData.object, "object");
  exactKeys(objectData, ["name", "source_recipe_version"], "object");
  if (typeof objectData.name !== "string" || !objectData.name || objectData.source_recipe_version !== "0.6") {
    fail("object", "expected a named v0.6 source");
  }
  const coordinateSystem = record(packageData.coordinate_system, "coordinate_system");
  if (Object.entries(COORDINATE_SYSTEM).some(([key, expected]) => coordinateSystem[key] !== expected)
    || Object.keys(coordinateSystem).length !== Object.keys(COORDINATE_SYSTEM).length) {
    fail("coordinate_system", "unsupported coordinate contract");
  }
  const rawParts = array(packageData.parts, "parts");
  if (rawParts.length === 0) fail("parts", "expected a non-empty array");
  const parts = rawParts.map(part);
  if (new Set(parts.map((item) => item.id)).size !== parts.length) fail("parts", "duplicate part identifiers");
  const connections = array(packageData.connections, "connections").map(connection);
  if (new Set(connections.map((item) => item.id)).size !== connections.length) fail("connections", "duplicate connection identifiers");
  const partMap = new Map(parts.map((item) => [item.id, item]));
  for (const item of connections) {
    const sourcePart = partMap.get(item.part);
    const targetPart = partMap.get(item.target.part);
    if (!sourcePart || !targetPart) fail(`connections.${item.id}`, "references an unknown part");
    if (!sourcePart.anchors.some((entry) => entry.name === item.anchor)
      || !targetPart.anchors.some((entry) => entry.name === item.target.anchor)) {
      fail(`connections.${item.id}`, "references an unknown anchor");
    }
  }
  const vertexCount = parts.reduce((count, item) => count + item.geometry.vertices.length, 0);
  const faceCount = parts.reduce((count, item) => count + item.geometry.faces.length, 0);
  const edgeCount = parts.reduce((count, item) => count + item.geometry.edges.length, 0);
  if (vertexCount > MAX_VERTICES || faceCount > MAX_FACES || edgeCount > MAX_EDGES) {
    fail("parts", "aggregate resource limit exceeded");
  }
  return {
    format: PACKAGE_FORMAT,
    version: PACKAGE_VERSION,
    object: { name: objectData.name, source_recipe_version: "0.6" },
    coordinate_system: COORDINATE_SYSTEM,
    parts,
    connections,
  };
}

export function parseObjectPackage(source: string): ObjectPackage {
  let value: unknown;
  try {
    value = JSON.parse(source);
  } catch {
    throw new Error("Object Package is not valid JSON");
  }
  return loadObjectPackageData(value);
}