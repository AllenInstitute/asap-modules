import datetime
from functools import partial
import os
import tempfile

import numpy as np
import renderapi

from bokeh.palettes import Plasma256, Viridis256
from bokeh.plotting import figure, save
from bokeh.layouts import row
from bokeh.models import (HoverTool, ColumnDataSource,
                          CustomJS, CategoricalColorMapper,
                          LinearColorMapper,
                          TapTool, OpenURL, Div, ColorBar,
                          Tabs, TabPanel)

from asap.residuals import compute_residuals as cr

try:
    # Python 2
    xrange
except NameError:
    # Python 3, xrange is now named range
    xrange = range


try:
    # Python 2
    xrange
except NameError:
    # Python 3, xrange is now named range
    xrange = range


def bbox_tup_to_xs_ys(bbox_tup):
    min_x, min_y, max_x, max_y = bbox_tup
    return (
        [min_x, max_x, max_x, min_x, min_x],
        [min_y, min_y, max_y, max_y, min_y]
    )


def tilespecs_to_xs_ys(tilespecs):
    return zip(*(bbox_tup_to_xs_ys(ts.bbox) for ts in tilespecs))


def point_match_plot(tilespecsA, matches, tilespecsB=None, match_max=500):
    if tilespecsB is None:
        tilespecsB = tilespecsA

    if len(matches) > 0:
        tId_to_ctr_a = {
            idx: (x, y)
            for x, y, idx in zip(*cr.get_tile_centers(tilespecsA))}
        tId_to_ctr_b = {
            idx: (x, y)
            for x, y, idx in zip(*cr.get_tile_centers(tilespecsB))}

        xs = []
        ys = []
        clist = []

        # tiny line to make sure zero is in there for consistent color range
        xs.append([0, 0])
        ys.append([0, 0.1])
        clist.append(0)

        # tiny line to make sure max is in there for consistent color range
        xs.append([0.1, 0])
        ys.append([0.1, 0.1])

        # if (set(tId_to_ctr_a.keys()) != set(tId_to_ctr_b.keys())):
        #     clist.append(500)
        # else:
        #     clist.append(200)
        clist.append(match_max)

        for m in matches:
            match_qId = m['qId']
            match_pId = m['pId']
            num_pts = len(m['matches']['q'][0])

            try:
                a_ctr = tId_to_ctr_a[match_qId]
                b_ctr = tId_to_ctr_b[match_pId]
            except KeyError:
                continue

            xs.append([a_ctr[0], b_ctr[0]])
            ys.append([a_ctr[1], b_ctr[1]])
            clist.append(num_pts)

        mapper = LinearColorMapper(
            palette=Plasma256, low=min(clist), high=max(clist))
        colorbar = ColorBar(
            color_mapper=mapper, label_standoff=12, location=(0, 0))
        source = ColumnDataSource(dict(xs=xs, ys=ys, colors=clist))

        TOOLS = "pan,box_zoom,reset,hover,save"

        w = np.ptp(xs)
        h = np.ptp(ys)
        base_dim = 1000
        if w > h:
            h = int(np.round(base_dim * (h / w)))
            w = base_dim
        else:
            h = base_dim
            w = int(np.round(base_dim * w / h))

        plot = figure(
            # plot_width=800, plot_height=700,
            width=w, height=h,
            background_fill_color='gray', tools=TOOLS,
            # sizing_mode="stretch_both",
            match_aspect=True
        )
        plot.tools[1].match_aspect = True
        plot.multi_line(
            xs="xs", ys="ys", source=source,
            color={'field': 'colors', 'transform': mapper}, line_width=2)
        plot.add_layout(colorbar, 'right')
        plot.xgrid.visible = False
        plot.ygrid.visible = False

    else:
        plot = figure(
            # width=800, height=700,
            background_fill_color='gray')

    return plot


def plot_residual(xs, ys, residual, residual_max=None):
    w = np.ptp(xs)
    h = np.ptp(ys)
    base_dim = 1000
    if w > h:
        h = int(np.round(base_dim * (h / w)))
        w = base_dim
    else:
        h = base_dim
        w = int(np.round(base_dim * w / h))
    p = figure(width=w, height=h)
    if residual_max is None:
        residual_max = max(residual)
    color_mapper = LinearColorMapper(
        palette=Viridis256, low=min(residual), high=residual_max)

    source = ColumnDataSource(data=dict(x=xs, y=ys, residual=residual))

    pglyph = p.patches(
        'x', 'y', source=source,
        fill_color={'field': 'residual', 'transform': color_mapper},
        fill_alpha=1.0, line_color="black", line_width=0.05)

    color_bar = ColorBar(color_mapper=color_mapper, label_standoff=12,
                         border_line_color=None, location=(0, 0))

    p.add_layout(color_bar, 'right')

    p.xgrid.visible = False
    p.ygrid.visible = False

    return p


def plot_residual_tilespecs(
        tspecs, tileId_to_point_residuals, default_residual=50, residual_max=None):
    tile_residual_mean = cr.compute_mean_tile_residuals(
        tileId_to_point_residuals)
    xs, ys = tilespecs_to_xs_ys(tspecs)
    residual = [
        tile_residual_mean.get(ts.tileId, default_residual)
        for ts in tspecs
    ]

    return plot_residual(xs, ys, residual, residual_max=residual_max)


def montage_defect_plot(
        tspecs, matches, disconnected_tiles, gap_tiles,
        seam_centroids, stats, z, tile_url_format=None):
    xs, ys = tilespecs_to_xs_ys(tspecs)
    alphas = [0.5] * len(xs)

    fill_color = []
    label = []
    gap_tiles = set(gap_tiles)
    disconnected_tiles = set(disconnected_tiles)

    tile_ids = [ts.tileId for ts in tspecs]

    label, fill_color = zip(*(
        (("Gap tiles", "red") if tileId in gap_tiles
         else ("Disconnected tiles", "yellow") if tileId in disconnected_tiles
         else ("Stitched tiles", "blue"))
        for tileId in tile_ids))

    color_mapper = CategoricalColorMapper(
        factors=['Gap tiles', 'Disconnected tiles', 'Stitched tiles'],
        palette=["red", "yellow", "blue"])
    source = ColumnDataSource(
        data=dict(x=xs, y=ys, alpha=alphas, names=tile_ids,
                  fill_color=fill_color, labels=label))

    seam_source = ColumnDataSource(data=dict(
        x=(seam_centroids[:, 0] if len(seam_centroids) else []),
        y=(seam_centroids[:, 1] if len(seam_centroids) else []),
        lbl=["Seam Centroids" for s in xrange(len(seam_centroids))]))

    TOOLS = "pan,box_zoom,reset,hover,tap,save"

    w = np.ptp(xs)
    h = np.ptp(ys)
    base_dim = 1000
    if w > h:
        h = int(np.round(base_dim * (h / w)))
        w = base_dim
    else:
        h = base_dim
        w = int(np.round(base_dim * w / h))

    p = figure(title=str(z),
               # width=1000, height=1000,
               width=w, height=h,
               tools=TOOLS,
               match_aspect=True)
    p.tools[1].match_aspect = True
    pp = p.patches(
        'x', 'y', source=source,
        alpha='alpha', line_width=2,
        color={'field': 'labels', 'transform': color_mapper},
        legend_group='labels')
    cp = p.scatter('x', 'y', source=seam_source, legend_group='lbl', size=11)

    jscode = """
        var inds = cb_obj.selected['1d'].indices;
        var d = cb_obj.data;
        var line = "<span style='float:left;clear:left;font_size=0.5pt'><br>" + d['%s'][inds[0]] + "</b></span>\\n";
        var text = div.text.concat(line);
        var lines = text.split("\\n")
        if ( lines.length > 35 ) { lines.shift(); }
        div.text = lines.join("\\n");
    """
    div = Div(width=w)
    layout = row(p, div)

    if tile_url_format:
        taptool = p.select(type=TapTool)
        taptool.renderers = [pp]
        taptool.callback = OpenURL(url=tile_url_format)

    hover = p.select(dict(type=HoverTool))
    hover.renderers = [pp]
    hover.point_policy = "follow_mouse"
    hover.tooltips = [("tileId", "@names"), ("x", "$x{int}"), ("y", "$y{int}")]

    source.js_event_callbacks['identify'] = [
        CustomJS(args=dict(div=div), code=jscode % ('names'))
    ]
    return layout


def create_montage_qc_plots(
        tspecs, matches, disconnected_tiles, gap_tiles,
        seam_centroids, stats, z, tile_url_format=None,
        match_max=500, residual_max=None):
    # montage qc
    layout = montage_defect_plot(
        tspecs, matches, disconnected_tiles, gap_tiles,
        seam_centroids, stats, z, tile_url_format=tile_url_format)

    # add point match plot in another tab
    plot = point_match_plot(tspecs, matches, match_max=match_max)

    # montage statistics plots in other tabs
    stat_layout = plot_residual_tilespecs(
        tspecs, stats["tile_residuals"],
        residual_max=residual_max
    )

    tabs = []
    tabs.append(TabPanel(child=layout, title="Defects"))
    tabs.append(TabPanel(child=plot, title="Point match plot"))
    tabs.append(TabPanel(child=stat_layout, title="Mean tile residual"))

    plot_tabs = Tabs(tabs=tabs)

    return plot_tabs


def write_montage_qc_plots(out_fn, plt):
    return save(plt, out_fn)


def run_montage_qc_plots_legacy(render, stack, out_html_dir, args):
    tspecs = args[0]
    matches = args[1]
    disconnected_tiles = args[2]
    gap_tiles = args[3]
    seam_centroids = np.array(args[4])
    stats = args[5]
    z = args[6]

    out_html = os.path.join(
        out_html_dir,
        "%s_%d_%s.html" % (
            stack,
            z,
            datetime.datetime.now().strftime('%Y%m%d%H%S%M%f')))
    tile_url_format = f"{render.DEFAULT_HOST}:{render.DEFAULT_PORT}/render-ws/v1/owner/{render.DEFAULT_OWNER}/project/{render.DEFAULT_PROJECT}/stack/{stack}/tile/@names/withNeighbors/jpeg-image?scale=0.1"

    qc_plot = create_montage_qc_plots(
        tspecs, matches, disconnected_tiles, gap_tiles,
        seam_centroids, stats, z, tile_url_format=tile_url_format)
    write_montage_qc_plots(out_html, qc_plot)
    return out_html


def plot_section_maps(
        render, stack, post_tspecs, matches, disconnected_tiles,
        gap_tiles, seam_centroids, stats, zvalues,
        out_html_dir=None, pool_size=5):
    if out_html_dir is None:
        out_html_dir = tempfile.mkdtemp()

    mypartial = partial(
        run_montage_qc_plots_legacy, render, stack, out_html_dir
    )

    args = zip(post_tspecs, matches, disconnected_tiles, gap_tiles,
               seam_centroids, stats, zvalues)

    with renderapi.client.WithPool(pool_size) as pool:
        html_files = pool.map(mypartial, args)

    return html_files
