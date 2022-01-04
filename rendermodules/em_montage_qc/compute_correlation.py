import renderapi
import numpy as np 
import cv2
import time
import multiprocessing as mp 
import networkx as nx 
import os
import PIL
import random
from shapely.geometry import Polygon
import rtree.index as rindex
from functools import partial

try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache

ex = {
    "render": {
        "host": "em-131db2",
        "port": 8080,
        "owner": "TEM",
        "project": "17797_1R",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts",
    },
    "stack": "em_2d_montage_solved_py",
    "z": 120218,
    "kernel_size": 0.01,
    "match_collection": "default_point_matches"
}

def compute_correlation(ptspec, qtspec, imp, imq, kernel_size=30):
    # translate the two images into the same coordinates
    dx = qtspec.tforms[-1].B0 - ptspec.tforms[-1].B0
    dy = qtspec.tforms[-1].B1 - ptspec.tforms[-1].B1

    trans0 = np.float32([ [1, 0, 0], [0, 1, 0] ])
    trans1 = np.float32([ [1, 0, dx], [0, 1, dy] ])

    (rows, cols) = ims[1].shape 
    ic0 = cv2.equalizeHist(
            cv2.warpAffine(imp,
                           trans0,
                           (cols + np.int(np.ceil(dx)),
                           rows + np.int(np.ceil(dy)))))
    ic1 = cv2.equalizeHist(
            cv2.warpAffine(imq,
                           trans1,
                           (cols + np.int(np.ceil(dx)),
                           rows + np.int(np.ceil(dy)))))   

    # mask out the non-overlapping area
    m0 = np.ma.masked_where(ic0 == 0, ic0)
    m1 = np.ma.masked_where(ic1 == 0, ic1)
    common_mask = ~((~m0.mask) & (~m1.mask))
    m0.mask = common_mask
    m1.mask = common_mask

    kern = (kernel_size, kernel_size)
    m0 = np.array(m0.filled(fill_value=0), dtype=float)
    m1 = np.array(m1.filled(fill_value=0), dtype=float)
    ave_m0 = cv2.blur(m0, kern)
    ave_m1 = cv2.blur(m1, kern)
    pr = (m0-ave_m0)*(m1-ave_m1)
    cpr = cv2.blur(pr, kern)

    return cpr

    # get non-zero values' indices for m0 and m1
    #ind0 = np.ma.nonzero(m0)
    #ind1 = np.ma.nonzero(m1)

    #minx, maxx = [min[ind0[0]], max[ind0[0]]]
    #miny, maxy = [min[ind0[1]], max[ind0[1]]] 

    #crop_img1 = m0[minx:maxx, miny:maxy]
    #crop_img2 = m1[minx:maxx, miny:maxy]

    # compute Normalized cross correlation between these two images


@lru_cache(maxsize=40)
def get_image_from_tspec(tspec, render):
    img = renderapi.client.render_tilespec(tspec, render=render)
    return img

def max_degree_nodes(G):
    # finds the list of max degree nodes in the graph G
    degree_list = list(nx.degree(G))
    degrees = [d[1] for d in degree_list]
    maximum = max(degrees)
    max_list = [d[0] for d in degree_list if d[1]==maximum]
    return max_list


def construct_affinity_graph(resolved_tspecs):
    tileids = {}
    bboxes = {}
    for ts in resolved_tspecs.tilespecs:
        bboxes[ts.tileId] = Polygon(ts.bbox_transformed(reference_tforms=resolved_tspecs.transforms))
    
    G = nx.Graph()

    # create an rtree to find intersecting polygons
    ridx = rindex.Index()
    for i, ts in enumerate(resolved_tspecs.tilespecs):
        tileids[ts.tileId] = i
        ridx.insert(i, ts.bbox)

    for i, ts in enumerate(resolved_tspecs.tilespecs):
        nodes = list(ridx.intersection(ts.bbox))
        nodes.remove(i)
        [G.add_edge(i, node) for node in nodes]
    
    # get the node list with max degree
    max_list = max_degree_nodes(G)

    #pick a random entry from this list
    max_node = random.choice(max_list)

    # get the list of tilepair indices in BFS order
    bfs_edges = list(nx.edge_bfs(G, max_node))

    return bfs_edges


def process_images(render, resolved_tspecs, bfs_edge):
    # get tilespecs
    ptspec = resolved_tspecs[bfs_edge[0]]
    qtspec = resolved_tspecs[bfs_edge[1]]

    pimg = get_image_from_tspec(ptspec, render)
    qimg = get_image_from_tspec(qtspec, render)

    #corr_image, similarity_score = compute_correlation(ptspec, qtspec, pimg, qimg)
    corr_image = compute_correlation(ptspec, qtspec, pimg, qimg)
    print(bfs_edge)
    return corr_image#, similarity_score

class ComputeCorrelation():

    def run(self, example):
        render = renderapi.connect(**ex['render'])
        # get resolved tilespecs
        resolved_tspecs = renderapi.resolvedtiles.get_resolved_tiles_from_z(ex['stack'], ex['z'], render=render)

        refids = np.array([r.transformId for r in resolved_tspecs.transforms])

        for i, tspec in enumerate(resolved_tspecs.tilespecs):
            for m in range(len(tspec.tforms)):
                if isinstance(tspec.tforms[m], renderapi.transform.ReferenceTransform):
                    rind = np.argwhere(refids == tspec.tforms[m].refId)[0][0]
                    tspec.tforms[m] = resolved_tspecs.transforms[rind]

        #print(resolved_tspecs.tilespecs[0])

        bfs_edges = construct_affinity_graph(resolved_tspecs)
        #print(bfs_edges)
        print(len(bfs_edges))

        mypartial = partial(process_images, render, resolved_tspecs.tilespecs)

        with renderapi.client.WithPool(10) as pool:
            img = pool.map(mypartial, bfs_edges)

if __name__=="__main__":
    mod = ComputeCorrelation()
    mod.run(ex)
        


