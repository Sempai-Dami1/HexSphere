// XY, YZ, ZX order matches rotate_vertices(). Nulls delimit wireframe segments.
export function rotateCoordinates(trace, angles) {
  const pairs = [[0, 1], [1, 2], [2, 0]];
  const trig = angles.map(angle => [Math.cos(angle * Math.PI / 180), Math.sin(angle * Math.PI / 180)]);
  const output = [[], [], []];
  for (let n = 0; n < trace.x.length; n++) {
    if (trace.x[n] == null) {
      output.forEach(axis => axis.push(null));
      continue;
    }
    const point = [trace.x[n], trace.y[n], trace.z[n]];
    pairs.forEach(([a, b], index) => {
      const [cos, sin] = trig[index];
      const first = point[a], second = point[b];
      point[a] = first * cos - second * sin;
      point[b] = first * sin + second * cos;
    });
    point.forEach((value, axis) => output[axis].push(value));
  }
  return {x: output[0], y: output[1], z: output[2]};
}

export function anglesAt(command, nowSeconds) {
  const elapsed = Math.max(0, nowSeconds - command.epoch);
  return command.angles.map((angle, axis) => {
    const value = angle + command.spins[axis] * command.degrees_per_second * elapsed;
    return ((value + 180) % 360 + 360) % 360 - 180;
  });
}

const instances = new WeakMap();

function draw(state, operation) {
  state.pending = (state.pending || Promise.resolve()).then(() => {
    if (!state.disposed) return operation();
  });
  return state.pending;
}

export function viewportSize(element) {
  // WebGL backing buffers use whole pixels. Measure the host, whose size is
  // controlled by Streamlit, rather than Plotly's own mutable descendants.
  return {width: Math.floor(element.getBoundingClientRect().width), height: 680};
}

export default function(component) {
  const {parentElement, data} = component;
  const plot = parentElement.querySelector('.hexsphere-plot');
  plot.dataset.spins = data.spins.join(',');
  plot.dataset.ready = 'false';
  let state = instances.get(parentElement);
  if (!state) {
    state = {generation: 0, frame: 0, disposed: false, sourceSignature: null};
    instances.set(parentElement, state);
    state.observer = new ResizeObserver(() => {
      cancelAnimationFrame(state.resizeFrame);
      state.resizeFrame = requestAnimationFrame(async () => {
        if (state.pending) await state.pending;
        if (state.disposed || !plot.isConnected || !plot._fullLayout) return;
        const size = viewportSize(parentElement);
        if (size.width <= 0 || (size.width === state.width && size.height === state.height)) return;
        state.width = size.width;
        state.height = size.height;
        // The sole resize path shares the draw queue with rotation updates.
        draw(state, () => window.Plotly.relayout(plot, {width: size.width, height: size.height}));
        try { await state.pending; } catch (error) { console.error(error); }
      });
    });
    state.observer.observe(parentElement);
  }
  state.disposed = false;
  state.command = data;
  const generation = ++state.generation;
  cancelAnimationFrame(state.frame);
  const cleanup = () => {
    // Data reconciliation can also call cleanup. A previous render's cleanup
    // must not cancel a newer command, or destroy a still-connected plot.
    if (state.generation === generation) {
      ++state.generation;
      cancelAnimationFrame(state.frame);
    }
    setTimeout(() => {
      if (!plot.isConnected && instances.get(parentElement) === state) {
        state.disposed = true;
        cancelAnimationFrame(state.resizeFrame);
        state.observer.disconnect();
        window.Plotly.purge(plot);
        instances.delete(parentElement);
      }
    }, 0);
  };

  if (!state.source && !data.figure) {
    if (!state.waitingForSource) {
      state.waitingForSource = true;
      component.setTriggerValue('source_needed', true);
    }
    return cleanup;
  }
  if (data.figure) {
    state.figure = data.figure;
    state.waitingForSource = false;
  }

  const sourceSignature = `${data.source_revision}:${data.camera_revision}`;
  const reconcile = async () => {
    // Wait for an outstanding coordinate update before reconciling appearance.
    if (state.pending) await state.pending;
    if (state.disposed || generation !== state.generation) return;
    if (sourceSignature !== state.sourceSignature) {
      state.source = state.figure.data;
      const layout = structuredClone(state.figure.layout);
      const size = viewportSize(parentElement);
      state.width = Math.max(size.width, 1);
      state.height = size.height;
      Object.assign(layout, {autosize: false, width: state.width, height: state.height});
      layout.scene = {...layout.scene, uirevision: `camera:${data.camera_revision}`};
      if (plot._fullLayout && state.cameraRevision === data.camera_revision) {
        layout.scene.camera = structuredClone(plot._fullLayout.scene.camera);
      }
      // A rotation-invariant envelope keeps long meshes and tangent decals in
      // frame, without changing ranges or resetting the orbit camera each frame.
      let radius = 0;
      for (const trace of state.source) {
        for (let n = 0; n < trace.x.length; n++) {
          if (trace.x[n] != null) radius = Math.max(radius, Math.hypot(trace.x[n], trace.y[n], trace.z[n]));
        }
      }
      // Auto-scale fits the rotation envelope. In manual mode keep the unscaled
      // envelope so Scale still enlarges/shrinks the object instead of being
      // canceled by a simultaneous range resize.
      radius = Math.max(radius * 1.05 / data.framing_scale, 0.01);
      for (const axis of ['xaxis', 'yaxis', 'zaxis']) {
        layout.scene[axis] = {...layout.scene[axis], range: [-radius, radius], autorange: false};
      }
      layout.scene.aspectmode = 'cube';
      const traces = state.source.map(trace => ({...trace, ...rotateCoordinates(trace, anglesAt(data, Date.now() / 1000))}));
      draw(state, () => window.Plotly.react(plot, traces, layout, {responsive: false, displaylogo: false, scrollZoom: true}));
      await state.pending;
      if (state.disposed || generation !== state.generation) return;
      state.sourceSignature = sourceSignature;
      state.cameraRevision = data.camera_revision;
    } else {
      await updateCoordinates();
    }
    if (!state.disposed && generation === state.generation) {
      plot.dataset.ready = 'true';
      if (data.spins.some(Boolean)) state.frame = requestAnimationFrame(tick);
    }
  };

  const updateCoordinates = () => {
    const angles = anglesAt(state.command, Date.now() / 1000);
    const coordinates = state.source.map(trace => rotateCoordinates(trace, angles));
    // Only XYZ changes: colors, opacity, finish, topology, and camera stay put.
    const update = {
      x: coordinates.map(trace => trace.x),
      y: coordinates.map(trace => trace.y),
      z: coordinates.map(trace => trace.z),
    };
    return draw(state, () => window.Plotly.restyle(plot, update, state.source.map((_, index) => index)));
  };

  let lastFrame = 0;
  const tick = async timestamp => {
    if (state.disposed || generation !== state.generation) return;
    // Smooth time-based motion, capped at 30 renders/sec. No overlapping draws,
    // queued stale frames, Python reruns, or network messages per frame.
    if (timestamp - lastFrame >= 1000 / 30 && !document.hidden) {
      lastFrame = timestamp;
      try {
        if (state.pending) await state.pending;
        if (state.disposed || generation !== state.generation) return;
        await updateCoordinates();
      } catch (error) { console.error(error); return; }
    }
    if (!state.disposed && generation === state.generation) state.frame = requestAnimationFrame(tick);
  };

  reconcile().catch(error => { plot.textContent = `Viewer error: ${error.message}`; });
  return cleanup;
}
