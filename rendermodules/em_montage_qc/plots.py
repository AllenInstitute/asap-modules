import numpy as np
import tempfile
import renderapi
import requests
from functools import partial

from rendermodules.residuals import compute_residuals as cr

from bokeh.palettes import Plasma256, Viridis256
from bokeh.plotting import figure, output_file, show, save
from bokeh.layouts import column, row
from bokeh.models.widgets import Tabs, Panel
from bokeh.models import (HoverTool, ColumnDataSource, 
                          CustomJS, CategoricalColorMapper,
                          LinearColorMapper, 
                          TapTool, OpenURL, Div, ColorBar,
                          Slider, WidgetBox)


def point_match_plot(tilespecsA, matches, tilespecsB=None):
    if tilespecsB is None:
        tilespecsB = tilespecsA
    
    if len(matches) > 0:
        x1, y1, id1 = cr.get_tile_centers(tilespecsA)
        x2, y2, id2 = cr.get_tile_centers(tilespecsB)

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
        
        if (set(x1) != set(x2)):
            clist.append(500)
        else:
            clist.append(200)
        
        for k in np.arange(len(matches)):
            t1 = np.argwhere(id1 == matches[k]['qId']).flatten()
            t2 = np.argwhere(id2 == matches[k]['pId']).flatten()
            if (t1.size != 0) & (t2.size != 0):
                t1 = t1[0]
                t2 = t2[0]
                xs.append([x1[t1], x2[t2]])
                ys.append([y1[t1], y2[t2]])
                clist.append(len(matches[k]['matches']['q'][0]))
        
        mapper = LinearColorMapper(palette=Plasma256, low=min(clist), high=max(clist))
        colorbar = ColorBar(color_mapper=mapper, label_standoff=12, location=(0,0))
        source = ColumnDataSource(dict(xs=xs, ys=ys, colors=clist))

        TOOLS = "pan,box_zoom,reset,hover,save"

        plot = figure(plot_width=800, plot_height=700, background_fill_color='gray', tools=TOOLS)
        plot.multi_line(xs="xs", ys="ys", source=source, color={'field':'colors', 'transform':mapper}, line_width=2)
        plot.add_layout(colorbar, 'right')
        plot.xgrid.visible = False
        plot.ygrid.visible = False

    else:
        plot = figure(plot_width=800, plot_height=700, background_fill_color='gray')
    
    return plot


def plot_residual(xs, ys, residual):
    p = figure(width=1000, height=1000)
    color_mapper = LinearColorMapper(palette=Viridis256, low=min(residual), high=max(residual))

    source = ColumnDataSource(data=dict(x=xs, y=ys, residual=residual))

    pglyph = p.patches('x', 'y', source=source, fill_color={'field':'residual', 'transform':color_mapper}, fill_alpha=1.0, line_color="black", line_width=0.05)

    color_bar = ColorBar(color_mapper=color_mapper, label_standoff=12, border_line_color=None, location=(0,0))

    p.add_layout(color_bar, 'right')

    p.xgrid.visible = False
    p.ygrid.visible = False

    #controls = WidgetBox(slider1, slider2)

    #layout = column(slider1, slider2, p)
    #layout = row(p, controls)
    return p


def plot_defects(render, stack, out_html_dir, args):
    tspecs = args[0]
    matches = args[1]
    dis_tiles = args[2]
    gap_tiles = args[3]
    seam_centroids = np.array(args[4])
    stats = args[5]
    z = args[6]

    # Tile residual mean
    tile_residual_mean = cr.compute_mean_tile_residuals(stats['tile_residuals'])

    tile_positions = []
    tile_ids = []
    residual = []
    for ts in tspecs:
        tile_ids.append(ts.tileId)
        pts = []
        pts.append([ts.minX, ts.minY])
        pts.append([ts.maxX, ts.minY])
        pts.append([ts.maxX, ts.maxY])
        pts.append([ts.minX, ts.maxY])
        pts.append([ts.minX, ts.minY])
        tile_positions.append(pts)
        
        if ts.tileId in tile_residual_mean.keys():
            residual.append(tile_residual_mean[ts.tileId])
        else:
            residual.append(50) # a high value for residual for that tile

    out_html = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode='w', dir=out_html_dir)
    out_html.close()

    output_file(out_html.name)
    xs = []
    ys = []
    alphas = []
    for tp in tile_positions:
        sp = np.array(tp)
        x = list(sp[:,0])
        y = list(sp[:,1])
        xs.append(x)
        ys.append(y)
        alphas.append(0.5)

    fill_color = []
    label = []
    for t in tile_ids:
        if t in gap_tiles:
            label.append("Gap tiles")
            fill_color.append("red")
        elif t in dis_tiles:
            label.append("Disconnected tiles")
            fill_color.append("yellow")
        else:
            label.append("Stitched tiles")
            fill_color.append("blue")

    color_mapper = CategoricalColorMapper(factors=['Gap tiles', 'Disconnected tiles', 'Stitched tiles'], palette=["red", "yellow", "blue"])
    source = ColumnDataSource(data=dict(x=xs, y=ys, alpha=alphas, names=tile_ids, fill_color=fill_color, labels=label))

    seam_source = ColumnDataSource(data=dict(
        x=(seam_centroids[:, 0] if len(seam_centroids) else []),
        y=(seam_centroids[:, 1] if len(seam_centroids) else []),
        lbl=["Seam Centroids" for s in xrange(len(seam_centroids))]))

    TOOLS = "pan,box_zoom,reset,hover,tap,save"

    p = figure(title=str(z), width=1000, height=1000, tools=TOOLS, match_aspect=True)
    pp = p.patches('x', 'y', source=source, alpha='alpha', line_width=2, color={'field':'labels', 'transform': color_mapper}, legend='labels')
    cp = p.circle('x', 'y', source=seam_source, legend='lbl', size=11)

    jscode = """
        var inds = cb_obj.selected['1d'].indices;
        var d = cb_obj.data;
        var line = "<span style='float:left;clear:left;font_size=0.5pt'><br>" + d['%s'][inds[0]] + "</b></span>\\n";
        var text = div.text.concat(line);
        var lines = text.split("\\n")
        if ( lines.length > 35 ) { lines.shift(); }
        div.text = lines.join("\\n");
    """
    div = Div(width=1000)
    layout = row(p, div)

    urls = "%s:%d/render-ws/v1/owner/%s/project/%s/stack/%s/tile/@names/png-image?scale=0.1"%(render.DEFAULT_HOST, render.DEFAULT_PORT, render.DEFAULT_OWNER, render.DEFAULT_PROJECT, stack)
    urls = "%s:%d/render-ws/v1/owner/%s/project/%s/stack/%s/tile/@names/withNeighbors/jpeg-image?scale=0.1"%(render.DEFAULT_HOST, render.DEFAULT_PORT, render.DEFAULT_OWNER, render.DEFAULT_PROJECT, stack)

    taptool = p.select(type=TapTool)
    taptool.renderers = [pp]
    taptool.callback = OpenURL(url=urls)

    hover = p.select(dict(type=HoverTool))
    hover.renderers = [pp]
    hover.point_policy = "follow_mouse"
    hover.tooltips = [("tileId", "@names"), ("x", "$x{int}"), ("y", "$y{int}")]

    source.callback = CustomJS(args=dict(div=div), code=jscode%('names'))

    # add point match plot in another tab
    plot = point_match_plot(tspecs, matches)

    # montage statistics plots in other tabs

    stat_layout = plot_residual(xs, ys, residual)
    
    tabs = []
    tabs.append(Panel(child=layout, title="Defects"))
    tabs.append(Panel(child=plot, title="Point match plot"))
    tabs.append(Panel(child=stat_layout, title="Mean tile residual"))

    plot_tabs = Tabs(tabs=tabs)

    save(plot_tabs)

    return out_html.name


def plot_section_maps(render, stack, post_tspecs, matches, disconnected_tiles, gap_tiles, seam_centroids, stats, zvalues, out_html_dir=None, pool_size=5):
    if out_html_dir is None:
        out_html_dir = tempfile.mkdtemp()

    mypartial = partial(plot_defects, render, stack, out_html_dir)

    args = zip(post_tspecs, matches, disconnected_tiles, gap_tiles, seam_centroids, stats, zvalues)

    with renderapi.client.WithPool(pool_size) as pool:
        html_files = pool.map(mypartial, args)

    return html_files
