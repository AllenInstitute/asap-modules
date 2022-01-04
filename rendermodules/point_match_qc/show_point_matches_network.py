import renderapi
import matplotlib
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection
from functools import partial
import matplotlib.pyplot as plt
import matplotlib.colors
import numpy as np


example = {
    "render": {
        "host": "http://em-131db",
        "port": 8081,
        "owner": "timf",
        "project": "17797_1R",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts"
    },
    "zmin": 29,
    "zmax": 30,
    "maxdepth": 2,
    "nfig": 1,
    "collection": "default_point_matches",
    "matchowner": "timf",
    "stack": "em_2d_montage_solved_cloned",
    "output_dir": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch",
    "pool_size": 5
}


def get_tile_centers(render, stack, z):
    # given a z, use renderapi to get the tile center coordinates, and tile ids
    tspecs = renderapi.tilespec.get_tile_specs_from_z(stack, float(z), render=render)
    xc = []
    yc = []
    tid = []
    for t in tspecs:
        xc.append(0.5*t.bbox[0]+t.bbox[2])
        yc.append(0.5*t.bbox[1]+t.bbox[3])
        tid.append(t.tileId)
    return np.array(xc), np.array(yc), np.array(tid)

def get_point_match_count_between_sections(render, stack, collection, owner, groupIds):
    pGroupId = groupIds[0]
    qGroupId = groupIds[1]
    x1,y1,id1 = get_tile_centers(render, stack, pGroupId)
    x2,y2,id2 = get_tile_centers(render, stack, qGroupId)

    # get the point matches
    pm = render.run(renderapi.pointmatch.get_matches_from_group_to_group, collection, pGroupId, qGroupId, owner=owner)

    lclist = [] # will hold coordinates of line segments (between tile pairs)
    clist = [] # will hold number of point match pairs, used as color

    # tiny line to make sure zero is in there for consistent color range
    tmp = []
    tmp.append((0,0))
    tmp.append((0,0.1))
    lclist.append(tmp)
    clist.append(0)

    # tiny line to make sure max is in there for consistent color range
    tmp = []
    tmp.append((0.1, 0.1))
    tmp.append((0, 0.1))
    lclist.append(tmp)
    clist.append(500) # the max number of point matches set

    if len(pm) != 0:
        for p in pm:
            # find the tilespecs
            k1 = np.argwhere(id1==p['qId']).flatten()
            k2 = np.argwhere(id2==p['pId']).flatten()
            if (k1.size != 0) & (k2.size != 0):
                k1 = k1[0]
                k2 = k2[0]
                tmp = []
                tmp.append((x1[k1],y1[k1]))
                tmp.append((x2[k2],y2[k2]))
                lclist.append(tmp)
                clist.append(len(p['matches']['q'][0]))

    return lclist, clist

def plot_point_match_count(lclist, clist, pdf):
    cmap = plt.cm.plasma_r
    fig = plt.figure(1, figsize=(11.69, 8.27))
    fig.clf()
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 580000)
    ax.set_ylim(0, 580000)

    LC = LineCollection(lclist, cmap=cmap)
    LC.set_array(np.array(clist))
    ax.add_collection(LC)
    fig = plt.gcf()
    ax.set_aspect('equal')
    ax.patch.set_color([0.5,0.5,0.5]) # gray background, easier to see yellow
    ax.set_title('Point match count plot')
    fig.colorbar(LC)
    plt.show()
    pdf.savefig(fig)

if __name__=="__main__":
    render = renderapi.connect(**example['render'])
    groups = renderapi.pointmatch.get_match_groupIds(example['collection'], render=render, owner=example['matchowner'])
    #print(groups)

    mypartial = partial(get_point_match_count_between_sections, render, example['stack'], example['collection'], example['matchowner'])
    with renderapi.client.WithPool(example['pool_size']) as pool:
        lclist, clist = pool.map(mypartial, zip(groups, groups))

    pdf = PdfPages('%s.pdf'%example['collection'])

    for lcl, cl in zip(lclist, clist):
        plot_point_match_count(lcl, cl, pdf)
    pdf.close()
    #for g in groups:
    #    lclist, clist = get_point_match_count_between_sections(render, example['stack'], example['collection'], example['matchowner'], g, g)
    #    plot_point_match_count(lclist, clist)
