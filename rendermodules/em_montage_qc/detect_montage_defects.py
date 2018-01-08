from functools import partial
from rtree import index as rindex
import networkx as nx
import renderapi
from rendermodules.em_montage_qc.schemas import DetectMontageDefectsParameters
from ..module.render_module import RenderModule
from rendermodules.em_montage_qc.plots import plot_section_maps

example = {
    "render":{
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "prestitched_stack": "mm2_acquire_8bit",
    "poststitched_stack": "mm2_acquire_8bit_Montage",
    "matchCollectionOwner": "gayathri_MM2",
    "matchCollection": "mm2_acquire_8bit_montage",
    "plot_sections":"True",
    "zstart": 1086,
    "zend": 1087,
    "pool_size": 20
}

def detect_disconnected_tiles(render, prestitched_stack, poststitched_stack, z):

    # get the tilespecs for both prestitched_stack and poststitched_stack
    pre_tilespecs = render.run(
                        renderapi.tilespec.get_tile_specs_from_z,
                        prestitched_stack,
                        z)
    post_tilespecs = render.run(
                        renderapi.tilespec.get_tile_specs_from_z,
                        poststitched_stack,
                        z)

    # pre tile_ids
    pre_tileIds = []
    pre_tileIds = [ts.tileId for ts in pre_tilespecs]

    # post tile_ids
    post_tileIds = []
    post_tileIds = [ts.tileId for ts in post_tilespecs]

    missing_tileIds = list(set(pre_tileIds) - set(post_tileIds))
    return missing_tileIds

def detect_stitching_gaps(render, prestitched_stack, poststitched_stack, z):
    # setup an rtree to find overlapping tiles
    pre_ridx = rindex.Index()

    # setup a graph to store overlapping tiles
    G1 = nx.Graph()

    # get the tilespecs for both prestitched_stack and poststitched_stack
    pre_tilespecs = render.run(
                        renderapi.tilespec.get_tile_specs_from_z,
                        prestitched_stack,
                        z)
    tilespecs = render.run(
                        renderapi.tilespec.get_tile_specs_from_z,
                        poststitched_stack,
                        z)

    # insert the prestitched_tilespecs into rtree with their bounding boxes to find overlaps
    [pre_ridx.insert(i, (ts.minX, ts.minY, ts.maxX, ts.maxY)) for i, ts in enumerate(pre_tilespecs)]

    pre_tileIds = {}
    for i, ts in enumerate(pre_tilespecs):
        pre_tileIds[ts.tileId] = i
        nodes = list(pre_ridx.intersection((ts.minX, ts.minY, ts.maxX, ts.maxY)))
        nodes.remove(i)
        [G1.add_edge(i, node) for node in nodes]


    # G1 contains the prestitched_stack tiles and the degree of each node representing
    # the number of tiles that overlap
    # This overlap count has to match in the poststitched_stack

    G2 = nx.Graph()
    post_ridx = rindex.Index()

    [post_ridx.insert(pre_tileIds[ts.tileId], (ts.minX, ts.minY, ts.maxX, ts.maxY)) for ts in tilespecs]

    for ts in tilespecs:
        i = pre_tileIds[ts.tileId]
        nodes = list(post_ridx.intersection((ts.minX, ts.minY, ts.maxX, ts.maxY)))
        nodes.remove(i)
        [G2.add_edge(i, node) for node in nodes]


    # Now G1 and G2 have the same index for the same tileId
    # comparing the degree of each node pre and post stitching should reveal stitching gaps
    #tileIds = nx.get_node_attributes(G2, 'tileId')
    gap_tiles = []
    for n in G2.nodes():
        if G1.degree(n) > G2.degree(n):
            tileId = pre_tileIds.keys()[pre_tileIds.values().index(n)]
            gap_tiles.append(tileId)

    return gap_tiles

def detect_stitching_mistakes(render, prestitched_stack, poststitched_stack, zvalues, pool_size=20):
    mypartial1 = partial(detect_disconnected_tiles, render, prestitched_stack, poststitched_stack)
    mypartial2 = partial(detect_stitching_gaps, render, prestitched_stack, poststitched_stack)

    disconnected_tiles = []
    gap_tiles = []

    with renderapi.client.WithPool(pool_size) as pool:
        disconnected_tiles = pool.map(mypartial1, zvalues)
        gap_tiles = pool.map(mypartial2, zvalues)

    return disconnected_tiles, gap_tiles


class DetectMontageDefects(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = DetectMontageDefectsParameters
        super(DetectMontageDefects, self).__init__(
            schema_type=schema_type, *args, **kwargs)

    def run(self):
        zvalues1 = self.render.run(renderapi.stack.get_z_values_for_stack,
                                self.args['poststitched_stack'])
        zrange = range(self.args['zstart'], self.args['zend']+1)
        zvalues = list(set(zvalues1).intersection(set(zrange)))

        disconnected_tiles, gap_tiles = detect_stitching_mistakes(
                                            self.render,
                                            self.args['prestitched_stack'],
                                            self.args['poststitched_stack'],
                                            zvalues,
                                            self.args['pool_size'])

        holes = [z for (z, dt) in zip(zvalues, disconnected_tiles) if len(dt) > 0]
        gaps = [z for (z, gt) in zip(zvalues, gap_tiles) if len(gt) > 0]
        #holes = [1086]
        #gaps = [1087]
        combinedz = holes + gaps
        
        if len(combinedz) > 0:
            if self.args['plot_sections']:
                self.args['out_html'] = plot_section_maps(self.render, self.args['poststitched_stack'], combinedz, out_html=self.args['out_html'])

        print(self.args['out_html'])
        return holes, gaps

if __name__ == "__main__":
    mod = DetectMontageDefects(input_data=example)
    mod.run()
