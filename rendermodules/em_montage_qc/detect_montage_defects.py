from functools import partial
from rtree import index as rindex
from scipy.spatial import KDTree
import networkx as nx
import numpy as np
import renderapi
from rendermodules.residuals import compute_residuals as cr
from rendermodules.em_montage_qc.schemas import DetectMontageDefectsParameters, DetectMontageDefectsParametersOutput
from ..module.render_module import RenderModule
from rendermodules.em_montage_qc.plots import plot_section_maps

example = {
    "render":{
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "danielk",
        "project": "Seams",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "prestitched_stack": "2_sections_near_crack_fine_lam_1e3",
    "poststitched_stack": "2_sections_near_crack_fine_lam_1e3_omitted",
    "match_collection_owner": "danielk",
    "match_collection": "NewPMS_combined_with_montage",
    "plot_sections":"True",
    "minZ": 1028,
    "maxZ": 1029,
    "pool_size": 20
}

'''
example = {
    "render":{
        "host": "http://em-131db",
        "port": 8081,
        "owner": "timf",
        "project": "STAGE",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "prestitched_stack": "em_2d_montage_lc_clone_20180112",
    "poststitched_stack": "em_2d_montage_solved_clone_20180112",
    "match_collection_owner": "timf",
    "match_collection": "default_point_matches",
    "minZ": 103,
    "maxZ": 107,
    "pool_size": 10
}
'''

def detect_seams(render, stack, match_collection, match_owner, z, residual_threshold=4, distance=60, min_cluster_size=7):
    # seams will always be computed for montages using montage point matches
    # but the input stack can be either montage, rough, or fine

    # Compute residuals and other stats for this z
    stats = cr.compute_residuals_within_group(render, stack, match_owner, match_collection, z)
    
    # get mean positions of the point matches as numpy array
    pt_match_positions = np.empty((0,2))
    for p in stats['pt_match_positions']:
        pt_match_positions = np.append(pt_match_positions, stats['pt_match_positions'][p], axis=0)

    # get the tile residuals
    tile_residuals = np.empty((0,1))
    for t in stats['tile_residuals']:
        tile_residuals = np.append(tile_residuals, stats['tile_residuals'][t])

    # threshold the points based on residuals
    new_pts = []
    new_residuals = []
    for p, tr in zip(pt_match_positions, tile_residuals):
        if tr >= residual_threshold:
            new_pts.append(p)
    
    new_pts = np.array(new_pts)

    # construct a KD Tree using these points
    tree = KDTree(new_pts)

    # construct a networkx graph
    G = nx.Graph()

    # iterate through each point to get its nearest neighbors within a distance
    for m, npt in enumerate(new_pts):
        idx = tree.query_ball_point(npt, r=distance)
        
        # add edge to G for each neighbor
        [G.add_edge(m, id) for id in idx]

    # get the connected subraphs from G
    Gc = nx.connected_component_subgraphs(G)

    # find the clusters that have more than specified number of nodes
    centroids = []
    for s in Gc:
        if len(s.nodes()) > min_cluster_size:
            pts = new_pts[s.nodes(),:]
            # get the centroid of these points that give the approximate location of the seam
            x_pts = pts[:,0]
            y_pts = pts[:,1]
            centroids.append([np.sum(x_pts)/len(pts), np.sum(y_pts)/len(pts)])
    
    return centroids

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

def detect_stitching_mistakes(render, prestitched_stack, poststitched_stack, match_collection, match_collection_owner, residual_threshold, neighbor_distance, min_cluster_size, zvalues, pool_size=20):
    mypartial1 = partial(detect_disconnected_tiles, 
                         render, 
                         prestitched_stack, 
                         poststitched_stack)
    mypartial2 = partial(detect_stitching_gaps, 
                         render, 
                         prestitched_stack, 
                         poststitched_stack)
    mypartial3 = partial(detect_seams, 
                         render, 
                         poststitched_stack, 
                         match_collection, 
                         match_collection_owner, 
                         residual_threshold=residual_threshold, 
                         distance=neighbor_distance,
                         min_cluster_size=min_cluster_size)

    disconnected_tiles = []
    gap_tiles = []
    seam_centroids = []

    with renderapi.client.WithPool(pool_size) as pool:
        disconnected_tiles = pool.map(mypartial1, zvalues)
        gap_tiles = pool.map(mypartial2, zvalues)
        seam_centroids = pool.map(mypartial3, zvalues)

    #for z in zvalues:
    #    seam_centroids = detect_seams(render, poststitched_stack, match_collection, match_collection_owner, z, distance=80)

    return disconnected_tiles, gap_tiles, seam_centroids


class DetectMontageDefectsModule(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = DetectMontageDefectsParameters
        super(DetectMontageDefectsModule, self).__init__(
            schema_type=schema_type, *args, **kwargs)
        
        default_output_schema = DetectMontageDefectsParametersOutput

    def run(self):
        zvalues1 = self.render.run(renderapi.stack.get_z_values_for_stack,
                                self.args['poststitched_stack'])
        zrange = range(self.args['minZ'], self.args['maxZ']+1)
        zvalues = list(set(zvalues1).intersection(set(zrange)))

        if len(zvalues) == 0:
            self.logger.error('No valid zvalues found in stack for given range {} - {}'.format(self.args['minZ'], self.args['maxZ']))

        disconnected_tiles, gap_tiles, seam_centroids = detect_stitching_mistakes(
                                                            self.render,
                                                            self.args['prestitched_stack'],
                                                            self.args['poststitched_stack'],
                                                            self.args['match_collection'],
                                                            self.args['match_collection_owner'],
                                                            self.args['residual_threshold'],
                                                            self.args['neighbors_distance'],
                                                            self.args['min_cluster_size'],
                                                            zvalues,
                                                            pool_size=self.args['pool_size'])

        holes = [z for (z, dt) in zip(zvalues, disconnected_tiles) if len(dt) > 0]
        gaps = [z for (z, gt) in zip(zvalues, gap_tiles) if len(gt) > 0]
        seams = [z for (z,sm) in zip(zvalues, seam_centroids) if len(sm) > 0]
        
        combinedz = holes + gaps + seams

        self.args['output_html'] = self.args['out_html_dir']
        if len(combinedz) > 0:
            if self.args['plot_sections']:
                self.args['output_html'] = plot_section_maps(self.render, self.args['poststitched_stack'], combinedz, out_html=self.args['output_html'])
                #print(self.args['output_html'])
        
        self.output({'output_html':self.args['output_html'], 
                     'hole_sections': holes,
                     'gap_sections':gaps,
                     'seam_sections':seams,
                     'seam_centroids':seam_centroids})

            

if __name__ == "__main__":
    mod = DetectMontageDefectsModule(input_data=example)
    mod.run()
