"""smooth_dash.py — one function that makes a Dash graph update smoothly.

SIT225 5C.

    app = Dash(__name__)
    layout, add_point = smooth_graph(app, ["x", "y", "z"], y_range=(-2, 2))
    app.layout = layout

    add_point({"x": 0.1, "y": -0.3, "z": -0.98})    # whenever data arrives

    app.run()
"""

import time
import threading

import plotly.graph_objects as go
from dash import dcc, html, Input, Output, Patch
from dash.exceptions import PreventUpdate


def smooth_graph(app, names, window=15, fps=10, y_range=None, title=""):
    """Add a smoothly-updating live graph to a Dash app.

    app     : your Dash app
    names   : list of line names, e.g. ["x", "y", "z"]
    window  : how many seconds of data to show at once
    fps     : how many times a second the graph updates
    y_range : (low, high) to fix the y axis, or None to let it scale itself
    title   : chart title

    Returns (layout, add_point).
    """
    waiting = []                  # points that have arrived but are not drawn yet
    lock = threading.Lock()       # data arrives on another thread, so we need this
    start = time.time()

    # ---- 1. the user calls this when new data arrives ----------------------
    def add_point(values):
        with lock:
            waiting.append((time.time() - start, values))

    # ---- 2. an empty graph with one line per name --------------------------
    figure = go.Figure()
    for name in names:
        figure.add_trace(go.Scatter(x=[], y=[], mode="lines", name=name))
    figure.update_layout(
        title=title,
        uirevision="keep",            # <- keeps the user's zoom when we update
        xaxis=dict(range=[0, window], title="Seconds"),
        yaxis=dict(range=list(y_range) if y_range else None),
        height=400,
    )

    layout = html.Div([
        dcc.Graph(id="smooth-graph", figure=figure),
        dcc.Interval(id="smooth-timer", interval=int(1000 / fps)),
    ])

    # ---- 3. add the waiting points to the lines ----------------------------
    # "extendData" tells Plotly to ADD to the lines already on screen, instead
    # of drawing a new graph. This is the bit that stops the flicker.
    @app.callback(Output("smooth-graph", "extendData"),
                  Input("smooth-timer", "n_intervals"))
    def draw_new_points(_):
        with lock:
            batch = list(waiting)
            waiting.clear()

        if not batch:
            raise PreventUpdate       # nothing new, do nothing

        times = [point[0] for point in batch]
        lines = []
        for name in names:
            lines.append([point[1][name] for point in batch])

        return (
            dict(x=[times] * len(names), y=lines),
            list(range(len(names))),  # which lines to add to
            1000,                     # keep the newest 1000 points
        )

    # ---- 4. slide the time window so the graph scrolls ---------------------
    # Patch() changes ONE thing (the x axis range) instead of the whole graph.
    @app.callback(Output("smooth-graph", "figure"),
                  Input("smooth-timer", "n_intervals"))
    def slide_window(_):
        left = max(0, (time.time() - start) - window)
        patch = Patch()
        patch["layout"]["xaxis"]["range"] = [left, left + window]
        return patch

    return layout, add_point
