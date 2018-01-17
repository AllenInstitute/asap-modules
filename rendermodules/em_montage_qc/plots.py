import numpy as np
#import matplotlib.pyplot as plt
#import matplotlib as mpl
#from matplotlib.collections import PatchCollection
#from matplotlib.patches import Polygon
#import matplotlib.cm as cm
import tempfile
import renderapi
from functools import partial
import pathos.multiprocessing as mp

from bokeh.plotting import figure, output_file, show, save
from bokeh.layouts import column
from bokeh.models import HoverTool, ColumnDataSource



def get_tile_ids_and_tile_boundaries(render, input_stack, z):
    # read the tilespecs for the z
    tilespecs = render.run(renderapi.tilespec.get_tile_specs_from_z, input_stack, z)
    tile_positions = []
    tile_ids = []

    for ts in tilespecs:
        tile_ids.append(ts.tileId)
        pts = []
        pts.append([ts.minX, ts.minY])
        pts.append([ts.maxX, ts.minY])
        pts.append([ts.maxX, ts.maxY])
        pts.append([ts.minX, ts.maxY])
        pts.append([ts.minX, ts.minY])
        tile_positions.append(pts)

    #print(tile_positions)
    return {'tile_ids':tile_ids, 'tile_positions':tile_positions, 'z':z}

def plot_bokeh_section_maps(tile_data, out_html):
    # tile_positions and tile_ids are list of lists
    output_file(out_html)

    # bokeh plot options
    TOOLS = "pan,wheel_zoom,box_zoom,reset,hover,save"

    plots = []
    for ts in tile_data:
        z = ts['z']
        tpos = ts['tile_positions']
        tids = ts['tile_ids']
        f1 = figure(title=str(z),width=1000, height=1000, tools=TOOLS)

        xs = []
        ys = []
        alphas = []
        for tp in tpos:
            sp = np.array(tp)
            x = list(sp[:,0])
            y = list(sp[:,1])
            xs.append(x)
            ys.append(y)
            alphas.append(0.5)

        source = ColumnDataSource(data=dict(x=xs, y=ys, alpha=alphas, names=tids,))
        f1.patches('x', 'y', source=source, alpha='alpha', line_width=2)
        hover = f1.select_one(HoverTool)
        hover.point_policy = "follow_mouse"
        hover.tooltips = [("tileId", "@names"),]
        plots.append(f1)

    p = column(*plots)
    save(p)


def plot_section_maps(render, stack, zvalues, out_html=None, pool_size=5):
    if out_html is None:
        tempf = tempfile.NamedTemporaryFile(suffix=".html",
                                            delete=False,
                                            mode='w')
        tempf.close()
        out_html = tempf.name

    # Get the tileIds and tile bounds for each z
    mypartial = partial(get_tile_ids_and_tile_boundaries, render, stack)

    with mp.ProcessingPool(pool_size) as pool:
        tile_data = pool.map(mypartial, zvalues)
    #for z in zvalues:
    #    tile_data = get_tile_ids_and_tile_boundaries(render, stack, z)

    plot_bokeh_section_maps(tile_data, out_html)
    return out_html
