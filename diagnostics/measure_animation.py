import contextlib
import io
import json
import logging
import statistics
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.disable(logging.CRITICAL)
import streamlit_app as app
import picture_sphere

rows = []
for name in ('SimpleBlock', 'SimpleHexShpere', 'PictureSphere'):
    cfg = app.OBJECT_REGISTRY[name]
    params = {key: meta['default'] for key, meta in cfg['params'].items()}
    vertices, faces, edges = cfg['generator'](params)
    kwargs = {}
    if name == 'PictureSphere':
        data = app.st.session_state.picture_sphere_tile_data
        kwargs['face_colors'] = [data['tile_colors'][tile] for tile in data['face_tile_ids']]
        labels = picture_sphere.build_tile_label_decals(
            dict(enumerate(picture_sphere.generate_test_tile_labels(len(data['tile_centroids'])))),
            data['tile_centroids'], data['adjacency'], data['tile_colors'], params['radius'], num_layers=3,
        )
        kwargs['label_mesh'] = labels
    app.build_plotly_figure(vertices, faces, edges, **kwargs).to_json()
    rotate_times, build_times, json_times = [], [], []
    for frame in range(12):
        angles = (frame, frame / 2, -frame / 3)
        begin = time.perf_counter()
        app.rotate_vertices(vertices, angles)
        rotate_times.append((time.perf_counter() - begin) * 1000)
        begin = time.perf_counter()
        fig = app.build_plotly_figure(vertices, faces, edges, angles=angles, **kwargs)
        build_times.append((time.perf_counter() - begin) * 1000)
        begin = time.perf_counter()
        payload = fig.to_json()
        json_times.append((time.perf_counter() - begin) * 1000)
    rows.append(dict(object=name, vertices=len(vertices), faces=len(faces), edges=len(edges),
                     label_vertices=len(kwargs.get('label_mesh', ([],))[0]),
                     rotation_ms=round(statistics.median(rotate_times), 3),
                     figure_ms=round(statistics.median(build_times), 3),
                     serialization_ms=round(statistics.median(json_times), 3),
                     figure_bytes=len(payload.encode())))
output = Path(__file__).with_name('animation_baseline.json')
output.write_text(json.dumps(rows, indent=2), encoding='utf-8')
print(json.dumps(rows, indent=2))
