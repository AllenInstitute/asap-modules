import numpy as np
import tempfile
import renderapi
import requests
from functools import partial
from bokeh.plotting import figure, output_file, show, save
from bokeh.layouts import column, row
from bokeh.models import HoverTool, ColumnDataSource, CustomJS, CategoricalColorMapper, TapTool, OpenURL, Div



def plot_defects(render, stack, out_html_dir, args):
    tspecs = args[0]
    dis_tiles = args[1]
    gap_tiles = args[2]
    seam_centroids = np.array(args[3])
    z = args[4]

    tile_positions = []
    tile_ids = []
    for ts in tspecs:
        tile_ids.append(ts.tileId)
        pts = []
        pts.append([ts.minX, ts.minY])
        pts.append([ts.maxX, ts.minY])
        pts.append([ts.maxX, ts.maxY])
        pts.append([ts.minX, ts.maxY])
        pts.append([ts.minX, ts.minY])
        tile_positions.append(pts)
    
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

    seam_source = ColumnDataSource(data=dict(x=seam_centroids[:,0], y=seam_centroids[:,1], lbl=["Seam Centroids" for s in xrange(len(seam_centroids))]))

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
    save(layout)

    return out_html.name


def plot_section_maps(render, stack, post_tspecs, disconnected_tiles, gap_tiles, seam_centroids, zvalues, out_html_dir=None, pool_size=5):
    if out_html_dir is None:
        out_html_dir = tempfile.mkdtemp()
    
    mypartial = partial(plot_defects, render, stack, out_html_dir)

    args = zip(post_tspecs, disconnected_tiles, gap_tiles, seam_centroids, zvalues)

    with renderapi.client.WithPool(pool_size) as pool:
        html_files = pool.map(mypartial, args)
    
    return html_files

