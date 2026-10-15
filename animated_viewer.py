"""Local Plotly viewport adapter; authoring animation never enters interchange data."""

from pathlib import Path

import streamlit as st
from plotly.offline import get_plotlyjs


# Inline CCv2 registration uses the project's installed Plotly bundle, without a
# network dependency. The separately readable JS is supplied as an inline string.
_COMPONENT = st.components.v2.component(
    "hexsphere_animated_plotly",
    html='<div class="hexsphere-plot" style="height:680px;width:100%;min-width:0;overflow:hidden"></div>',
    js=get_plotlyjs() + "\n" + Path(__file__).with_name("animated_viewer.js").read_text(encoding="utf-8"),
    isolate_styles=False,
)


def render_animated_viewer(figure, *, source_revision, angles, spins, degrees_per_second, epoch, revision):
    """Send one source figure plus a time-based rotation command, never frame data."""
    signature = (source_revision, st.session_state.attach_vis_controls, id(_COMPONENT))
    send_source = st.session_state.get("_viewer_sent_signature") != signature
    st.session_state["_viewer_sent_signature"] = signature
    _COMPONENT(
        key="hexsphere_animated_viewer",
        data={
            "figure": figure if send_source else None,
            "source_revision": source_revision,
            "angles": list(angles), "spins": list(spins),
            "degrees_per_second": degrees_per_second, "epoch": epoch,
            "camera_revision": revision,
            "framing_scale": 1.0 if st.session_state.vis_auto_scale else st.session_state.vis_scale,
        },
        height=680,
        on_source_needed_change=lambda: st.session_state.pop("_viewer_sent_signature", None),
    )
