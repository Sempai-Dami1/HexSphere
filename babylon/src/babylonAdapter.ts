import {
  Color3,
  Mesh,
  MeshBuilder,
  Scene,
  StandardMaterial,
  Vector3,
  VertexBuffer,
  VertexData,
} from "@babylonjs/core";
import type { ObjectPackage, PackagePart } from "./objectPackage";

const PART_COLORS = [
  new Color3(0.18, 0.68, 0.62),
  new Color3(0.91, 0.55, 0.29),
  new Color3(0.56, 0.72, 0.39),
  new Color3(0.77, 0.48, 0.62),
];

function materialFor(scene: Scene, index: number): StandardMaterial {
  const material = new StandardMaterial(`package-part-material-${index}`, scene);
  material.diffuseColor = PART_COLORS[index % PART_COLORS.length];
  material.specularColor = new Color3(0.18, 0.2, 0.2);
  return material;
}

export function createPartMeshes(scene: Scene, packageData: ObjectPackage): Mesh[] {
  return packageData.parts.map((part, index) => createPartMesh(scene, part, index));
}

function createPartMesh(scene: Scene, part: PackagePart, index: number): Mesh {
  const mesh = new Mesh(part.id, scene);
  const positions = part.geometry.vertices.flatMap((vertex) => vertex);
  const indices = part.geometry.faces.flatMap((face) => face);
  const normals: number[] = [];
  VertexData.ComputeNormals(positions, indices, normals);
  mesh.setVerticesData(VertexBuffer.PositionKind, positions, true, 3);
  mesh.setVerticesData(VertexBuffer.NormalKind, normals, true, 3);
  mesh.setIndices(indices);
  mesh.position.setAll(0);
  mesh.rotation.setAll(0);
  mesh.scaling.setAll(1);
  mesh.material = materialFor(scene, index);
  mesh.metadata = {
    partId: part.id,
    type: part.type,
    transform: part.transform,
    anchors: part.anchors,
    edges: part.geometry.edges,
    data: part.metadata,
  };
  mesh.refreshBoundingInfo();
  return mesh;
}

export interface PackageOverlays {
  anchorMarkers: Mesh[];
  connectionLines: Mesh[];
  connectionMarkers: Mesh[];
}

export function createPackageOverlays(scene: Scene, packageData: ObjectPackage): PackageOverlays {
  const anchorMarkers: Mesh[] = [];
  for (const part of packageData.parts) {
    for (const anchor of part.anchors) {
      const marker = MeshBuilder.CreateSphere(`anchor-${part.id}-${anchor.name}`, { diameter: 0.11 }, scene);
      marker.position.copyFromFloats(...anchor.position);
      marker.material = overlayMaterial(scene, "anchor-marker-material", new Color3(0.24, 0.8, 0.92));
      marker.metadata = { partId: part.id, anchor };
      anchorMarkers.push(marker);
    }
  }

  const connectionLines = packageData.connections.map((connection) => {
    const line = MeshBuilder.CreateLines(`connection-${connection.id}`, {
      points: [new Vector3(...connection.source.position), new Vector3(...connection.target_anchor_frame.position)],
    }, scene);
    line.color = new Color3(1, 0.72, 0.25);
    line.metadata = { connection };
    return line;
  });
  const connectionMarkers = packageData.connections.map((connection) => {
    const marker = MeshBuilder.CreateSphere(`connection-marker-${connection.id}`, { diameter: 0.17 }, scene);
    marker.position.copyFromFloats(...connection.source.position);
    marker.material = overlayMaterial(scene, "connection-marker-material", new Color3(1, 0.68, 0.19));
    marker.metadata = { connection };
    return marker;
  });
  return { anchorMarkers, connectionLines, connectionMarkers };
}

function overlayMaterial(scene: Scene, name: string, color: Color3): StandardMaterial {
  const material = new StandardMaterial(name, scene);
  material.diffuseColor = color;
  material.emissiveColor = color.scale(0.28);
  return material;
}

export function createWorldAxes(scene: Scene, length = 2): Mesh[] {
  const origin = Vector3.Zero();
  return [
    axis(scene, "world-axis-x", origin, new Vector3(length, 0, 0), new Color3(0.94, 0.3, 0.29)),
    axis(scene, "world-axis-y", origin, new Vector3(0, length, 0), new Color3(0.38, 0.82, 0.5)),
    axis(scene, "world-axis-z", origin, new Vector3(0, 0, length), new Color3(0.34, 0.61, 0.98)),
  ];
}

function axis(scene: Scene, name: string, start: Vector3, end: Vector3, color: Color3): Mesh {
  const line = MeshBuilder.CreateLines(name, { points: [start, end] }, scene);
  line.color = color;
  return line;
}