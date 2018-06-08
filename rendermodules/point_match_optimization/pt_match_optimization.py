import os
import json
import renderapi
import itertools
import numpy as np 
import cv2
import shutil
import tempfile
import time
import urllib
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from numbers import Number
from functools import partial
from operator import itemgetter
from shapely.geometry import Polygon
from jinja2 import FileSystemLoader, Environment
from rendermodules.module.render_module import RenderModule
from rendermodules.point_match_optimization.schemas import PtMatchOptimizationParameters, PtMatchOptimizationParametersOutput


ex = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts"
    },
    "SIFT_options": {
        "SIFTfdSize": [4, 6, 8],
        "SIFTmaxScale": [0.82],
        "SIFTminScale": [0.28],
        "SIFTsteps": [4, 6, 8],
        "renderScale": [0.1, 0.2],
        "matchModelType": ["SIMILARITY", "RIGID", "AFFINE"]
    },
    "url_options":{
        "normalizeForMatching": "true",
        "renderWithFilter": "true",
        "renderWithoutMask": "true"
    },
    "outputDirectory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch/pmopts",
    "tile_stack": "point_match_optimization_test",
    "stack": "mm2_acquire_8bit_reimage_postVOXA_TEMCA2_rev1039",
    "tilepair_file": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch/fine/tilePairs/MM2/tile_pairs_mm2_acquire_8bit_reimage_postVOXA_TEMCA2_Rough_rev1039_v2_z_1023_to_1034_dist_2_p000.json",
    "filter_tilepairs":False,
    "no_tilepairs_to_test":5,
    "max_tilepairs_with_matches":4  
}

ex = {
    "render": {
        "host": "http://em-131db",
        "port": 8081,
        "owner": "timf",
        "project": "17797_1R",
        "client_scripts": "/allen/aibs/pipeline/image_processing/volume_assembly/render-jars/production/scripts"
    },
    "SIFT_options": {
        "SIFTfdSize": [4],
        "SIFTmaxScale": [0.82],
        "SIFTminScale": [0.28],
        "SIFTsteps": [8],
        "renderScale": [0.3],
        "matchModelType": ["AFFINE"]
    },
    "url_options":{
        "normalizeForMatching": "true",
        "renderWithFilter": "true",
        "renderWithoutMask": "true",
        "excludeAllTransforms": "false",
        "excludeFirstTransformAndAllAfter": "false",
        "excludeTransformsAfterLast": "false"
    },
    "outputDirectory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch/ptmatch",
    "tile_stack": "point_match_optimization_test",
    "stack": "em_2d_montage_apply_mipmaps",
    "tilepair_file": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch/17797_1R/tilepairs/temca4_tilepair_test.json",
    "filter_tilepairs":False,
    "no_tilepairs_to_test":4,
    "max_tilepairs_with_matches":4  
}


def polys_overlap(ts, buffer=0):
    ts1 = ts[0]
    ts2 = ts[1]
    p1 = Polygon(ts1.bbox_transformed(ndiv_inner=1))
    p2 = Polygon(ts2.bbox_transformed(ndiv_inner=1))
    return p1.intersects(p2)


'''
def get_canvas_url(render_args, stack, tile1, tile2, url_options):
    base_data_url = '%s:%d/render-ws/v1'%(render_args['host'], render_args['port'])
    tile_base_url = "%s/owner/%s/project/%s/stack/%s/tile"%(base_data_url,
                                                            render_args['owner'],
                                                            render_args['project'],
                                                            stack)
    url_suffix = "render-parameters"
    if url_options['renderWithFilter'] is False:
        url_suffix += '?filter=false'
    else:
        url_suffix += '?filter=true'
    if url_options['normalizeForMatching'] is False:
        url_suffix += '&normalizeForMatching=false'
    else:
        url_suffix += '&normalizeForMatching=true'
    if url_options['renderWithoutMask'] is False:
        url_suffix += '&renderWithoutMask=false'
    else:
        url_suffix += '&renderWithoutMask=true'

    canvas_urls = "%s/%s/%s %s/%s/%s"%(tile_base_url,
                                        tile1,
                                        url_suffix,
                                        tile_base_url,
                                        tile2,
                                        url_suffix)
    return canvas_urls
'''

def get_parameter_sets_and_strings(SIFT_options):
    #length = [len(x) for x in SIFT_options]
    #maxlen = np.max(length)

    new_options = {}
    all_parameter_list = []
    for key in SIFT_options:
        if (~isinstance(SIFT_options[key], list)):
            new_options[key] = list(SIFT_options[key])
        else:
            new_options[key] = SIFT_options[key]

    keys = []
    for n in new_options:
        keys.append(n)
        all_parameter_list.append(new_options[n])

    all_combinations = list(itertools.product(*all_parameter_list))
    #return all_parameter_list
    return keys, all_combinations

def render_from_template(directory, template_name, **kwargs):
    loader = FileSystemLoader(directory)
    env = Environment(loader=loader)
    template = env.get_template(template_name)
    return template.render(**kwargs)

def draw_matches(render, stack, tile1, tile2, ptmatches, scale, outdir, url_options, color=None):
    
    #im1_url = "%s:%d/render-ws/v1/owner/%s/project/%s/stack/%s/tile/%s/png-image?scale=%f&filter=%s&normalizeForMatching=%s"%(render.DEFAULT_HOST,
    #                render.DEFAULT_PORT,
    #                render.DEFAULT_OWNER,
    #                render.DEFAULT_PROJECT,
    #                stack,
    #                tile1,
    #                scale,
    #                url_options['renderWithFilter'],
    #                url_options['normalizeForMatching'])
    #im2_url = "%s:%d/render-ws/v1/owner/%s/project/%s/stack/%s/tile/%s/png-image?scale=%f&filter=%s&normalizeForMatching=%s"%(render.DEFAULT_HOST,
    #                render.DEFAULT_PORT,
    #                render.DEFAULT_OWNER,
    #                render.DEFAULT_PROJECT,
    #                stack,
    #                tile2,
    #                scale,
    #                url_options['renderWithFilter'],
    #                url_options['normalizeForMatching'])

    #r = urllib.urlopen(im1_url)
    #img1 = np.asarray(bytearray(r.read()), dtype="uint8")
    #img1 = cv2.imdecode(img1, cv2.IMREAD_COLOR)

    #r = urllib.urlopen(im2_url)
    #img2 = np.asarray(bytearray(r.read()), dtype="uint8")
    #img2 = cv2.imdecode(img2, cv2.IMREAD_COLOR)

    img1 = render.run(renderapi.image.get_tile_image_data, 
                      stack, 
                      tile1, 
                      normalizeForMatching=url_options['normalizeForMatching'],
                      scale=scale,
                      filter=url_options['renderWithFilter'])
    img2 = render.run(renderapi.image.get_tile_image_data,
                      stack,
                      tile2,
                      normalizeForMatching=url_options['normalizeForMatching'],
                      scale=scale,
                      filter=url_options['renderWithFilter'])

    if img1.shape > img2.shape:
        img2 = cv2.resize(img2, img1.shape)
    if img2.shape > img1.shape:
        img1 = cv2.resize(img1, img2.shape)
    
    if len(img1.shape) == 3:
        new_shape = (max(img1.shape[0], img2.shape[0]), img1.shape[1]+img2.shape[1], img1.shape[2])
    elif len(img1.shape) == 2:
        new_shape = (max(img1.shape[0], img2.shape[0]), img1.shape[1]+img2.shape[1])
    new_img = np.zeros(new_shape, type(img1.flat[0]))

    # place images onto the new image
    new_img[0:img1.shape[0], 0:img1.shape[1]] = img1
    new_img[0:img2.shape[0], img1.shape[1]:img1.shape[1]+img2.shape[1]] = img2

    # Draw lines between matches. Make sure to offset end coords n second image appropriately
    r = 5
    thickness = 2
    if ~(color is None):
        c = color

    if (len(ptmatches) > 0):
        ps = np.column_stack(ptmatches[0]['matches']['p'])
        qs = np.column_stack(ptmatches[0]['matches']['q'])

        #fig, ax = plt.subplots(1)
        #ax.imshow(new_img)

        for p, q in zip(ps, qs):
            # generate random color for RGB and grayscale images as needed
            if ~(color is None):
                c = np.random.randint(0,255,3) #if len(img1.shape) == 3 else np.random.randint(0,255)
            end1 = tuple(([int(pi*scale) for pi in p]))
            end2 = tuple(([int(qi*scale) for qi in q]))
            ad =  [img1.shape[1], 0]
            end2 = tuple([a+b for a,b in zip(end2, ad)])

            #ax.plot([end1[0], end2[0]], [end1[1], end2[1]], '-')
            cv2.line(new_img, end1, end2, c, thickness)
            cv2.circle(new_img, end1, r, c, thickness)
            cv2.circle(new_img, end2, r, c, thickness)

    tempfilename = tempfile.NamedTemporaryFile(prefix='matches_', suffix='.png', dir=outdir, delete=False)
    tempfilename.close()

    #plt.show()
    #plt.savefig(tempfilename)
    #print(tempfilename.name)
    cv2.imwrite(tempfilename.name, new_img)
    
    return tempfilename.name



def get_tile_pair_matched_image(render, stack, tileId1, tileId2, pGroupId, qGroupId, outdir, matchCollectionOwner, matchCollection, url_options, renderScale=0.1):
    im1 = '%s.jpg'%tileId1
    im2 = '%s.jpg'%tileId2
    im1 = os.path.join(outdir, "%s"%(renderScale), im1)
    im2 = os.path.join(outdir, "%s"%(renderScale), im2)
    
    # check if the point match collection exists
    collections = renderapi.pointmatch.get_matchcollections(owner=matchCollectionOwner, 
                                                            render=render)
    collectionIds = [f['collectionId']['name'] for f in collections]
    
    ptmatches = []
    if (matchCollection in collectionIds):
        ptmatches = renderapi.pointmatch.get_matches_from_tile_to_tile(matchCollection,
                                                                    pGroupId,
                                                                    tileId1,
                                                                    qGroupId,
                                                                    tileId2,
                                                                    owner=matchCollectionOwner,
                                                                    render=render)
    
    ptmatch_count = 0
    if (len(ptmatches) > 0):
        ptmatch_count = len(ptmatches[0]['matches']['p'][0])
    
    match_img_filename = draw_matches(render, stack, tileId1, tileId2, ptmatches, renderScale, outdir, url_options)
    return match_img_filename, ptmatch_count

'''
def compute_point_matches_for_tilepair(render, stack, url_options, option_keys, options, output_dir, tileID):
    return_struct = {}
    return_struct['zipped'] = []
    return_struct['img_url_count_zipped'] = []
    return_struct['match_img_filename'] = []
    return_struct['ptmatch_count'] = []
    return_struct['tilepair_url'] = []

    for op in options:
        argvs  = []
        #outdir = 'pmopt'
        collection_name = 'pms'
        renderScale = 0.1
        for param, value in zip(option_keys, op):
            if param == "renderScale":
                renderScale = value
            if type(value) is str:
                argvs += ['--%s'%(param), '"%s"'%value]
            else:
                argvs += ['--%s'%(param), value]
            #outdir += "_%s_%s"%(param, str(value))
            collection_name += '_%s'%(str(value).replace('.', 'D'))
        
        return_struct['collection_name'] = collection_name
        return_struct['outdir'] = output_dir

        tile1 = tileID['tileId1']
        tile2 = tileID['tileId2']
        pGroupId = tileID['pGroupId']
        qGroupId = tileID['qGroupId']
        
        # get canvas urls
        canvas_urls = get_canvas_url(render.DEFAULT_KWARGS, stack, tile1, tile2, url_options)

        baseDataUrl = renderapi.render.format_baseurl(render.DEFAULT_KWARGS['host'], render.DEFAULT_KWARGS['port'])
        argvs1 = argvs + ['--baseDataUrl', baseDataUrl]
        argvs1 += ['--owner', render.DEFAULT_KWARGS['owner']]
        argvs1 += ['--collection', collection_name]
        #argvs1 += ['--matchStorageFile', os.path.join(outdir, 'matches.json')]
        argvs1 += ['--debugDirectory', output_dir]
        argvs1 += ["", canvas_urls]

        # run the point match client
        renderapi.client.call_run_ws_client('org.janelia.render.client.PointMatchClient',
                                            add_args=argvs1,
                                            renderclient=render,
                                            memGB='2G')

        # rename the rendered image pairs to include renderscale for uniqueness
        img1 = '%s.jpg'%(tile1)
        img2 = '%s.jpg'%(tile2)

        im1 = '%s_%f.jpg'%(tile1, renderScale)
        im2 = '%s_%f.jpg'%(tile2, renderScale)
        if os.path.exists(os.path.join(output_dir, img1)):
            shutil.copy2(os.path.join(output_dir, img1), os.path.join(output_dir, im1))
        if os.path.exists(os.path.join(output_dir, img2)):
            shutil.copy2(os.path.join(output_dir, img2), os.path.join(output_dir, im2))
        
        # create the image showing the matched features and add it to an html file
        match_img_filename, ptmatch_count = get_tile_pair_matched_image(render,
                                                        stack,
                                                        tile1,
                                                        tile2,
                                                        pGroupId,
                                                        qGroupId,
                                                        output_dir,
                                                        render.DEFAULT_KWARGS['owner'],
                                                        collection_name,
                                                        renderScale)
        
        # create the tilepair url for this parameter setting
        tilepair_base_url = '%s:%d/render-ws/view/tile-pair.html'%(render.DEFAULT_KWARGS['host'], render.DEFAULT_KWARGS['port'])
        tilepair_base_url += '?renderStackOwner=%s'%(render.DEFAULT_KWARGS['owner'])
        tilepair_base_url += '&renderStackProject=%s'%(render.DEFAULT_KWARGS['project'])
        tilepair_base_url += '&renderStack=%s'%(stack)
        tilepair_base_url += '&renderScale=0.2'
        tilepair_base_url += '&matchOwner=%s'%(render.DEFAULT_KWARGS['owner'])
        tilepair_base_url += '&matchCollection=%s'%(collection_name)
        tilepair_base_url += '&pId=%s'%(tile1)
        tilepair_base_url += '&pGroupId=%s'%(pGroupId)
        tilepair_base_url += '&qId=%s'%(tile2)
        tilepair_base_url += '&qGroupId=%s'%(qGroupId)

        return_struct['match_img_filename'].append(match_img_filename)
        return_struct['tilepair_url'].append(tilepair_base_url)
        return_struct['ptmatch_count'].append(ptmatch_count)
        return_struct['zipped'].append(zip(option_keys, op))

    return_struct['img_url_count_zipped'] = zip(return_struct['match_img_filename'], return_struct['tilepair_url'], return_struct['ptmatch_count'], return_struct['zipped'])
    return return_struct
'''

def compute_point_matches(render, stack, tileID, output_dir, url_options, option_keys, options):
    
    return_struct = {}
    return_struct['options'] = options
    return_struct['keys'] = option_keys
    return_struct['zipped'] = zip(option_keys, options)
    return_struct['img_url_count_zipped'] = []
    return_struct['match_img_filename'] = []
    return_struct['ptmatch_count'] = []
    return_struct['tilepair_url'] = []

    collection_name = 'pms'
    ops = {}
    for param, value in zip(option_keys, options):
        ops[param] = value
        collection_name += '_%s'%(str(value).replace('.', 'D'))
    
    tileids = []
    for tID in tileID:
        tileids.append([tID['tileId1'], tID['tileId2']])
    
    renderapi.client.pointMatchClient(stack, 
                                      collection_name, 
                                      tileids, 
                                      SIFTfdSize=ops['SIFTfdSize'],
                                      SIFTmaxScale=ops['SIFTmaxScale'],
                                      SIFTminScale=ops['SIFTminScale'],
                                      SIFTsteps=ops['SIFTsteps'],
                                      matchIterations=ops['matchIterations'],
                                      matchMaxEpsilon=ops['matchMaxEpsilon'],
                                      matchMaxNumInliers=ops['matchMaxNumInliers'],
                                      matchMaxTrust=ops['matchMaxTrust'],
                                      matchMinInlierRatio=ops['matchMinInlierRatio'],
                                      matchMinNumInliers=ops['matchMinNumInliers'],
                                      matchModelType=ops['matchModelType'],
                                      matchRod=ops['matchRod'],
                                      renderScale=ops['renderScale'],
                                      filter=url_options['renderWithFilter'],
                                      renderWithoutMask=url_options['renderWithoutMask'],
                                      excludeAllTransforms=url_options['excludeAllTransforms'],
                                      excludeTransformsAfterLast=url_options['excludeTransformsAfterLast'],
                                      excludeFirstTransformAndAllAfter=url_options['excludeFirstTransformAndAllAfter'],
                                      host=render.DEFAULT_HOST,
                                      port=render.DEFAULT_PORT,
                                      owner=render.DEFAULT_OWNER,
                                      project=render.DEFAULT_PROJECT,
                                      client_script=os.path.join(render.DEFAULT_CLIENT_SCRIPTS,'run_ws_client.sh'),
                                      numberOfThreads=10)
    
    return_struct['collection_name'] = collection_name
    return_struct['outdir'] = output_dir

    for tID in tileID:
        tile1 = tID['tileId1']
        tile2 = tID['tileId2']
        pGroupId = tID['pGroupId']
        qGroupId = tID['qGroupId']

        # create the image showing the matched features and add it to an html file
        match_img_filename, ptmatch_count = get_tile_pair_matched_image(render,
                                                        stack,
                                                        tile1,
                                                        tile2,
                                                        pGroupId,
                                                        qGroupId,
                                                        output_dir,
                                                        render.DEFAULT_KWARGS['owner'],
                                                        collection_name,
                                                        url_options, 
                                                        ops['renderScale'])

        # create the tilepair url for this parameter setting
        tilepair_base_url = '%s:%d/render-ws/view/tile-pair.html'%(render.DEFAULT_KWARGS['host'], render.DEFAULT_KWARGS['port'])
        tilepair_base_url += '?renderStackOwner=%s'%(render.DEFAULT_KWARGS['owner'])
        tilepair_base_url += '&renderStackProject=%s'%(render.DEFAULT_KWARGS['project'])
        tilepair_base_url += '&renderStack=%s'%(stack)
        tilepair_base_url += '&renderScale=0.2'
        tilepair_base_url += '&matchOwner=%s'%(render.DEFAULT_KWARGS['owner'])
        tilepair_base_url += '&matchCollection=%s'%(collection_name)
        tilepair_base_url += '&pId=%s'%(tile1)
        tilepair_base_url += '&pGroupId=%s'%(pGroupId)
        tilepair_base_url += '&qId=%s'%(tile2)
        tilepair_base_url += '&qGroupId=%s'%(qGroupId)

        return_struct['match_img_filename'].append(match_img_filename)
        return_struct['tilepair_url'].append(tilepair_base_url)
        return_struct['ptmatch_count'].append(ptmatch_count)

    return_struct['img_url_count_zipped'] = zip(return_struct['match_img_filename'], return_struct['tilepair_url'], return_struct['ptmatch_count'])
    return return_struct


def filter_tile_pairs(stack, neighborPairs, render, pool_size=5):
    # returns a list of filtered tilepairs in the neighborPairs format
    do_overlap = []
    t0 = time.time()
    ts1 = [renderapi.tilespec.get_tile_spec(stack, id['p']['id'], render=render) for id in neighborPairs]
    ts2 = [renderapi.tilespec.get_tile_spec(stack, id['q']['id'], render=render) for id in neighborPairs]
    t1 = time.time()
    print(t1-t0)
    mypartial = partial(polys_overlap)
    with renderapi.client.WithPool(pool_size) as pool:
        do_overlap = pool.map(mypartial, zip(ts1, ts2))

    filtered_tilepairs = [np for np, do in zip(neighborPairs, do_overlap) if do == True]
    return filtered_tilepairs


class PtMatchOptimization(RenderModule):
    default_schema = PtMatchOptimizationParameters
    default_output_schema = PtMatchOptimizationParametersOutput

    '''
    def get_pt_match_matrix(self, keys, options, return_struct):
        pt_match_matrix = np.zeros((len(return_struct), self.args['no_tilepairs_to_test']), dtype=int)
        
        for i, r in enumerate(return_struct):
            pt_match_matrix[i, :] = r['ptmatch_count']
        
        # get the # of tilepairs that have pt matches for each parameter set
        non_zero_count = np.count_nonzero(pt_match_matrix, axis=1)

        # sort the non_zero_count to get the max count of tilepairs and parameters corresponding to it
        sorted_count = sorted(enumerate(non_zero_count), key=itemgetter(1))

        # Find the max and its first occurrence in the sorted_count
    '''

    def run(self):
        # read the tile pair file and extract random set of tilepairs
        tilepairf = {}
        with open(self.args['tilepair_file'], 'r') as f:
            tilepairf = json.load(f)
        f.close()

        tilepairs = tilepairf['neighborPairs']
        if self.args['filter_tilepairs']:
            # this takes a lot of time 
            tilepairs = filter_tile_pairs(self.args['stack'], tilepairf['neighborPairs'], self.render, self.args['pool_size'])
        
        # get no_tilepairs_to_test # of random integers
        tp_indices = np.random.choice(range(len(tilepairs)), self.args['no_tilepairs_to_test'], replace=False)
        
        tileIds = []
        ts = []
        for tp in tp_indices:
            tid = {}
            
            tileId1 = tilepairs[tp]['p']['id']
            tileId2 = tilepairs[tp]['q']['id']
            
            ts1 = renderapi.tilespec.get_tile_spec(self.args['stack'], tileId1, render=self.render)
            ts2 = renderapi.tilespec.get_tile_spec(self.args['stack'], tileId2, render=self.render)

            tid['tileId1'] = tileId1
            tid['tileId2'] = tileId2
            tid['pGroupId'] = ts1.layout.sectionId
            tid['qGroupId'] = ts2.layout.sectionId
            tileIds.append(tid)

            ts.append(ts1)
            ts.append(ts2)

        # create the tile stack
        if self.args['tile_stack'] is None:
            tile_stack = "pmopts_{}_t{}".format(self.args['stack'], time.strftime("%m%d%y_%H%M%S"))
            self.args['tile_stack'] = tile_stack

        renderapi.stack.create_stack(self.args['tile_stack'], render=self.render)
        renderapi.client.import_tilespecs(self.args['tile_stack'], ts, render=self.render)
        renderapi.stack.set_stack_state(self.args['tile_stack'], 'COMPLETE', render=self.render)

        # the order of these two lines matter
        keys, options = get_parameter_sets_and_strings(self.args['SIFT_options'])

        zipped = []
        for op in options:
            zipped.append(zip(keys, op))
        '''
        # mypartial with iterating over tilepairs rather than options
        mypartial = partial(compute_point_matches_for_tilepair,
                            self.render,
                            self.args['stack'],
                            self.args['url_options'],
                            keys,
                            options,
                            self.args['outputDirectory'])

        #with renderapi.client.WithPool(self.args['pool_size']) as pool:
        #    return_struct = pool.map(mypartial, tileIds)

        return_struct = []
        for tileids in tileIds:
            return_struct.append(compute_point_matches_for_tilepair(self.render, 
                                                                    self.args['stack'], 
                                                                    self.args['url_options'], 
                                                                    keys, 
                                                                    options, 
                                                                    self.args['outputDirectory'], 
                                                                    tileids))
        '''
        
        mypartial = partial(compute_point_matches,
                            self.render,
                            self.args['stack'],
                            tileIds,
                            self.args['outputDirectory'],
                            self.args['url_options'],
                            keys)
        
        #print(options)
        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            return_struct = pool.map(mypartial, options)
        
        #return_struct = []
        #for ops in options:
        #    return_struct.append(compute_point_matches(self.render, 
        #                                                self.args['stack'], 
        #                                                tileIds, 
        #                                                self.args['outputDirectory'], 
        #                                                self.args['url_options'], 
        #                                                keys, 
        #                                                ops))
        
        
        m = render_from_template(os.path.dirname(__file__), 'optimization_new.html', return_struct=return_struct, zipped=zipped)
        #m = render_from_template(os.path.dirname(__file__), 'optimization_tile.html', return_struct=return_struct, zipped=zipped)
    
        tempfilename = tempfile.NamedTemporaryFile(prefix='match_html_', suffix='.html', dir=self.args['outputDirectory'], delete=False)
        tempfilename.close()
        ff = open(tempfilename.name, "w")
        ff.write(m)
        ff.close()
        self.output({"output_html": tempfilename.name})
        

if __name__ == "__main__":
    module = PtMatchOptimization(input_data=ex)
    module.run()