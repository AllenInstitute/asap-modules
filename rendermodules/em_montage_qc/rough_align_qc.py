import renderapi
import numpy as np 
from math import pi
from shapely.geometry import Polygon
from shapely.ops import cascaded_union
import multiprocessing as mp 
import json
import requests
from functools import partial

import tempfile
import seaborn as sns
import matplotlib.pyplot as plt, mpld3
import matplotlib as mpl
from descartes.patch import PolygonPatch
from matplotlib.backends.backend_pdf import PdfPages
from bokeh.layouts import gridplot
from bokeh.io import show, save
from bokeh.plotting import figure, output_file
from bokeh.models import ColumnDataSource, Plot, LinearColorMapper, ColorBar, LinearAxis
from bokeh.models.annotations import Title
from bokeh.models.glyphs import Patches, Patch, Rect
from bokeh.models.widgets import Tabs, Panel
from bokeh.palettes import Plasma256, Viridis256

from ..module.render_module import RenderModule, RenderModuleException
from rendermodules.em_montage_qc.schemas import RoughQCSchema, RoughQCOutputSchema

example = {
    "render":{
        "host": "http://em-131db2",
        "port": 8080,
        "owner": "TEM",
        "project": "17797_1R",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts"
    },
    "input_downsampled_stack": "em_2d_montage_solved_py_0_01_mapped",
    "output_downsampled_stack": "em_rough_align_solved_downsample_zs27060_ze27586",
    "minZ": 27060,
    "maxZ": 27164,
    "pool_size": 20,
    "output_dir": "/home/gayathrim/Dropbox/render-modules",
    "out_file_format": 1
}



def get_poly(stack, render, z):
    s = requests.Session()
    s.mount('http://', requests.adapters.HTTPAdapter(max_retries=5))
    z = float(z) / 1.0
    rts = renderapi.resolvedtiles.get_resolved_tiles_from_z(stack, z, render=render, session=s)
    outpolys = []
    for tile in rts.tilespecs:
        bbox = tile.bbox_transformed(ndiv_inner=2, reference_tforms=rts.transforms)
        outpolys.append(Polygon(bbox))
    return cascaded_union(outpolys)


def plot_poly(axis, p, face, edge, alpha):
    (x1, xh) = axis.get_xlim()
    (y1, yh) = axis.get_ylim()

    if isinstance(p, Polygon):
        p = [p]
    
    for ip in p:
        axis.add_patch(PolygonPatch(ip, facecolor=face, edgecolor=edge, alpha=alpha))
        bounds = ip.bounds
        
        x1 = bounds[0] if bounds[0] < x1 else x1
        y1 = bounds[1] if bounds[1] < y1 else y1
        xh = bounds[2] if bounds[2] > xh else xh
        yh = bounds[3] if bounds[3] > yh else yh
    xr = xh-x1
    yr = yh-y1

    axis.set_xlim(x1-0.02*xr, xh+0.02*xr)
    axis.set_ylim(y1-0.02*yr, yh+0.02*yr)
    axis.set_aspect('equal')

def plot_bokeh_poly(p):
    if isinstance(p, Polygon):
        p = [p]
    
    xs = []
    ys = []

    #colors = ["#085494", "#f7fbff", "#9ecae1"]
    colors = ["red", "firebrick", "blue", "green"]
    nc = []
    
    for i, ip in enumerate(p):
        coords = ip.exterior.coords
        xx = np.array([x[0] for x in coords])
        yy = np.array([y[1] for y in coords])
        xs.append(xx)
        ys.append(yy)
        nc.append(colors[i])
        
    source = ColumnDataSource(data=dict(xs=xs, ys=ys))
    
    return source, nc

def plot_distortion_pdf(pre_poly, post_poly, dio, doi, distortion, zvalues, out_dir):
    out_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, mode='w', dir=out_dir)
    out_pdf.close()

    pdf = PdfPages(out_pdf.name)

    # plot the distortion values 
    fig = plt.figure()
    plt.scatter(zvalues, distortion)
    plt.title('Distortion values for Rough alignment')
    plt.xlabel("Z")
    plt.ylabel("distortion")
    pdf.savefig(fig)

    for i, z in enumerate(zvalues):
        fig, (ax1, ax2) = plt.subplots(1, 2)
    
        plot_poly(ax1, pre_poly[i], 'k', 'k', 0.5)
        plot_poly(ax1, post_poly[i], 'w', 'k', 0.5)
        plt.title('z = %d' % int(z))
        plt.xticks(fontsize=8)
        plt.yticks(fontsize=8)

        ax1.get_shared_x_axes().join(ax1, ax2)
        plot_poly(ax2, dio[i], 'r', 'k', 0.5)
        plot_poly(ax2, doi[i], 'g', 'k', 0.5)
        plt.title('Distortion = %0.3f' % distortion[i])
        plt.xticks(fontsize=8)
        plt.yticks(fontsize=8)

        for ax in [ax1, ax2]:
            if not ax.yaxis_inverted():
                ax.invert_yaxis()
    
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close()
    
    pdf.close()
    return out_pdf.name
    

def plot_distortion_bokeh(pre_poly, post_poly, dio, doi, distortion, zvalues):
    
    # plot the distortion values 
    fig = plt.figure()
    plt.scatter(zvalues, distortion)
    plt.title('Distortion values for Rough alignment')
    plt.xlabel("Z")
    plt.ylabel("distortion")
    
    figs = figure()
    figs.circle(zvalues, distortion, size=5, color="navy", alpha=0.5)
    figs.xaxis.axis_label = "Z"
    figs.yaxis.axis_label = "Distortion"
    figs.title.text = "Distortion values for Rough alignment"

    grid = []
    grid.append([figs, None])

    for i, z in enumerate(zvalues):
        plot1 = figure()
        plot2 = figure()

        source1, color1 = plot_bokeh_poly(pre_poly[i])
        source2, color2 = plot_bokeh_poly(post_poly[i])

        glyph = Patches(xs="xs", ys="ys", fill_color="gray", fill_alpha=1.0)
        plot1.add_glyph(source1, glyph=glyph)
        
        glyph = Patches(xs="xs", ys="ys", fill_color="lightgray", fill_alpha=1.0)
        plot1.add_glyph(source2, glyph=glyph)
        plot1.title.text = "Alignment before and After for z={}".format(z)
         
        source3, color3 = plot_bokeh_poly(dio[i])
        source4, color4 = plot_bokeh_poly(doi[i])

        glyph = Patches(xs="xs", ys="ys", fill_color="red", fill_alpha=0.5)
        plot2.add_glyph(source3, glyph)

        glyph = Patches(xs="xs", ys="ys", fill_color="white", fill_alpha=1.0)
        plot2.add_glyph(source4, glyph)
        plot2.title.text = "Distortion value for z={} is {}".format(z, distortion[i])
        
        grid.append([plot1, plot2])
   
    grids = gridplot(grid)
    return grids

def plot_ious_pdf(ious, zvalues, out_dir):
    out_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, mode='w', dir=out_dir)
    out_pdf.close()
    pdf = PdfPages(out_pdf.name)

    per_row = 50
    dz = (ious.shape[1]-1)/2
    ylabels = [str(z) for z in range(-dz, dz+1)]

    tabs = []
    # one figure for every 200 sections
    newz = []
    newiou = []
    for i in range(0, len(zvalues), 200):
        if i+199 > len(zvalues):
            newz = zvalues[i:]
            newiou = ious[i:,:]
        else:
            newz = zvalues[i:i+199]
            newiou = ious[i:i+199,:]

        if len(newz)%per_row == 0:
            rows = len(newz) / per_row
        else:
            rows = (len(newz) / per_row) + 1
        fig, ax = plt.subplots(nrows=rows, figsize=(6*rows, 3*rows))

        if rows > 1:
            for r in range(rows):
                start = r * per_row
                sns.heatmap(newiou[start:start+per_row].T, ax=ax[r], linewidth=0.5, vmin=0.7, vmax=1.0)
                ax[r].set_xticklabels([str(z) for z in newz[start:start+per_row]], rotation=90)
                ax[r].set_yticklabels(ylabels)
        else:
            sns.heatmap(newiou.T, ax=ax, linewidth=0.5, vmin=0.7, vmax=1.0)
            ax.set_xticklabels([str(z) for z in newz], rotation=90)
            ax.set_yticklabels(ylabels)
    
        plt.tight_layout()
        pdf.savefig(fig)
        
    pdf.close()
    
    return out_pdf.name

def plot_ious_bokeh(ious, zvalues):
    per_row = 50
    dz = (ious.shape[1]-1)/2
    ylabels = [z for z in range(-dz, dz+1)]

    mapper = LinearColorMapper(palette=Plasma256, low=0.0, high=1.0)
    colorbar = ColorBar(color_mapper=mapper, major_label_text_font_size="5pt", label_standoff=12, location=(0,0))
    tabs = []
    # one figure for every 200 sections
    newz = []
    newiou = []

    t = Title()
    t.text = "IOU Plot"
    xaxis = LinearAxis()
    yaxis = LinearAxis()
            
    for i in range(0, len(zvalues), 200):
        if i+199 > len(zvalues):
            newz = zvalues[i:]
            newiou = ious[i:,:]
        else:
            newz = zvalues[i:i+199]
            newiou = ious[i:i+199,:]
        
        if len(newz)%per_row == 0:
            rows = len(newz) / per_row
        else:
            rows = (len(newz) / per_row) + 1
        
        plots = []
            
        if rows > 1:
            #p.add_layout(xaxis, 'below')
            #p.add_layout(yaxis, 'left')
            
            for r in range(rows):
                start = r * per_row
                xvalues = np.ndarray.flatten(newiou[start:start+per_row])
                x_range1 = newz[start:start+per_row] #range(start, start+per_row+1)
                x_range = np.repeat(x_range1, len(ylabels))
                y_range = np.tile(ylabels, len(x_range1))
                
                source = ColumnDataSource(dict(x=x_range, y=y_range, iou=xvalues))
                p = figure(title=t, plot_width=400*rows, plot_height=100*rows)
                p.axis.axis_line_color = None
                p.axis.major_tick_line_color = None
                p.axis.major_label_text_font_size = "10pt"
                p.axis.major_label_standoff = 0
                #p.axis.major_label_orientation = 1.0
                '''
                glyph = Rect(x="x", y="y", 
                        width=1, height=1, 
                        fill_color={'field': 'iou', 'transform': mapper},
                        line_color=None)
                p.add_glyph(source, glyph)
                '''
                p.rect(x="x", y="y",
                        width=1, height=1,
                        source=source,
                        fill_color={'field':'iou', 'transform': mapper},
                        line_color=None)
                plots.append(p)
        #        tabs.append([p])
        else:
            xvalues = np.ndarray.flatten(newiou)
            x_range = np.repeat(zvalues, len(ylabels))
            y_range = [int(z) for z in ylabels]
            y_range = np.tile(y_range, len(zvalues))
            
            p = figure(title=t)
            source = ColumnDataSource(dict(x=x_range, y=y_range, iou=xvalues))
            glyph = Rect(x="x", y="y", 
                        width=1, height=1, 
                        fill_color={'field': 'iou', 'transform': mapper},
                        line_color=None)
            p.add_glyph(source, glyph)
            '''
            p = figure(title=t)
            source = ColumnDataSource(dict(x=x_range, y=y_range, iou=xvalues))
            p.rect(x="x", y="y", 
                    width=1, height=1, 
                    source=source,
                    fill_color={'field': 'iou', 'transform': mapper}, 
                    line_color=None)
            '''
            p.add_layout(colorbar, 'right')
            #show(p)
            #tabs.append([p])
            plots.append(p)
        tabs = [[p] for p in plots]

    grid = gridplot(tabs)
    return grid

def compute_ious(polys, zvalues):
    adjlist = [(x,y) for x,y in zip(zvalues, zvalues[1:]) if abs(x-y) == 1]
    
    #account for any missing zvalues
    diff = [(y+x)/2 for x, y in zip(zvalues, zvalues[1:]) if abs(x-y) > 1]
    # compute IoU
    ious = np.zeros((len(zvalues)+len(diff), 3))
    
    for adj in adjlist:
        poly1 = polys[adj[0]]
        poly2 = polys[adj[1]]
        inter = poly1.intersection(poly2)
        union_poly = cascaded_union([poly1, poly2])
        try:
            iou = inter.area / union_poly.area 
        except ZeroDivisionError:
            iou = 0
        i = adj[0]
        j = adj[1]
        ious[int(i-min(zvalues)), int(j-i+1)] = iou
        ious[int(j-min(zvalues)), int(i-j+1)] = iou
    
    return ious

def compute_distortion(inpoly, outpoly, z):
    dio = inpoly.difference(outpoly)
    doi = outpoly.difference(inpoly)
    distortion = np.round((dio.area + doi.area) / inpoly.area, 5)

    return dio, doi, distortion

def generate_bokeh_plots(ious, zrange, out_dir, pre_polys, post_polys, dio, doi, distortion, zvalues):
    out_html = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode='w', dir=out_dir)
    out_html.close()

    output_file(out_html.name)

    grids = plot_distortion_bokeh(pre_polys, post_polys, dio, doi, distortion, zvalues)
    iou_grids = plot_ious_bokeh(ious, zvalues)
    
    tabs = []
    tabs.append(Panel(child=grids, title="Distortion Plots"))
    tabs.append(Panel(child=iou_grids, title="IOU Plots"))
    plot_tabs = Tabs(tabs=tabs)

    save(plot_tabs)
    return out_html.name

def generate_pdf_plots(ious, zrange, out_dir, pre_polys, post_polys, dio, doi, distortion, zvalues):
    distortion_pdf = plot_distortion_pdf(pre_polys, post_polys, dio, doi, distortion, zvalues, out_dir)
    iou_pdf = plot_ious_pdf(ious, zvalues, out_dir)

    return distortion_pdf, iou_pdf


class RoughAlignmentQC(RenderModule):
    default_schema = RoughQCSchema
    default_output_schema = RoughQCOutputSchema

    def run(self):
        zvalues1 = self.render.run(renderapi.stack.get_z_values_for_stack,
                                self.args['output_downsampled_stack'])
        zrange = range(self.args['minZ'], self.args['maxZ']+1)
        zvalues = list(set(zvalues1).intersection(set(zrange)))
        zvalues.sort()
        if len(zvalues) == 0:
            raise RenderModuleException('No valid zvalues found in stack for given range {} - {}'.format(self.args['minZ'], self.args['maxZ']))

        # get the boundary polygon for each section
        mypartial1 = partial(get_poly, self.args['output_downsampled_stack'], self.render)
        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            boundary_polygons = pool.map(mypartial1, zvalues)

        post_polys = {}
        for poly, z in zip(boundary_polygons, zvalues):
            post_polys[z] = poly 

        mypartial2 = partial(get_poly, self.args['input_downsampled_stack'], self.render)
        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            pre_boundary_polygons = pool.map(mypartial2, zvalues)

        pre_polys = {}
        for poly, z in zip(pre_boundary_polygons, zvalues):
            pre_polys[z] = poly

        if self.args['output_dir'] is None:
            self.args['output_dir'] = tempfile.mkdtemp()

        # compute ious
        ious = compute_ious(post_polys, zvalues)
        #iou_plot = plot_ious(ious, zrange, self.args['output_dir'])

        # compute distortion
        distortion = []
        dio = []
        doi = []

        for i, z in enumerate(zvalues):
            di, do, dist = compute_distortion(pre_boundary_polygons[i], boundary_polygons[i], z)
            dio.append(di)
            doi.append(do)
            distortion.append(dist)
        
        dist_plt_name = None
        iou_plt_name = None
        if self.args['out_file_format'] == 0: # pdf plots
            dist_plt_name, iou_plt_name = generate_pdf_plots(ious, zrange, self.args['output_dir'], pre_boundary_polygons, 
                                                    boundary_polygons, dio, doi, distortion, zvalues)
        else:
            plot_name = generate_bokeh_plots(ious, zrange, self.args['output_dir'], pre_boundary_polygons, 
                                boundary_polygons, dio, doi, distortion, zvalues)
            dist_plt_name = plot_name
            iou_plt_name = plot_name
        
        self.output({"iou_plot": iou_plt_name, "distortion_plot": dist_plt_name})
        


if __name__ == "__main__":
    mod = RoughAlignmentQC(input_data=example)
    mod.run()
