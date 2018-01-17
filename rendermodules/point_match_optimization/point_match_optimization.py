import os
import json
import renderapi
import itertools
import numpy as np
import marshmallow as mm
import cv2
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import tempfile
from numbers import Number
from functools import partial
from marshmallow import Schema, fields
from jinja2 import FileSystemLoader, Environment
from rendermodules.module.render_module import RenderModule
from rendermodules.point_match_optimization.schemas import PointMatchOptimizationParameters, PointMatchOptimizationParametersOutput


ex = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "SIFT_options": {
        "SIFTfdSize": [8],
        "SIFTmaxScale": [0.82],
        "SIFTminScale": [0.28],
        "SIFTsteps": [3],
        "fillWithNoise": "false",
        "renderScale": [0.1, 0.35]
    },
    "outputDirectory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch/pmopts",
    "tile_stack": "point_match_optimization_test",
    "stack": "mm2_acquire_8bit_reimage",
    "tileId1": "20170830120417214_295434_5LC_0064_01_redo_001050_0_16_12.1050.0",
    "tileId2": "20170830120445578_295434_5LC_0064_01_redo_001050_0_16_13.1050.0",
    "url_options":{
        "normalizeForMatching": "true",
        "renderWithFilter": "true",
        "renderWithoutMask": "true"
    }
}

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


def get_parameter_sets_and_strings(SIFT_options):
    length = [len(x) for x in SIFT_options]
    maxlen = np.max(length)

    new_options = {}
    all_parameter_list = []
    for key in SIFT_options:
        if ~isinstance(SIFT_options[key], list):
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


def draw_matches(im1, im2, ptmatches, scale, color=None):
    img1 = mpimg.imread(im1)
    img2 = mpimg.imread(im2)

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
    if color:
        c = color

    if (len(ptmatches) > 0):
        ps = np.column_stack(ptmatches[0]['matches']['p'])
        qs = np.column_stack(ptmatches[0]['matches']['q'])

        #fig, ax = plt.subplots(1)
        #ax.imshow(new_img)

        for p, q in zip(ps, qs):
            # generate random color for RGB and grayscale images as needed
            if not color:
                c = np.random.randint(0,255,3) #if len(img1.shape) == 3 else np.random.randint(0,255)
            end1 = tuple(([int(pi*scale) for pi in p]))
            end2 = tuple(([int(qi*scale) for qi in q]))
            ad =  [img1.shape[1], 0]
            end2 = tuple([a+b for a,b in zip(end2, ad)])

            #ax.plot([end1[0], end2[0]], [end1[1], end2[1]], '-')
            cv2.line(new_img, end1, end2, c, thickness)
            cv2.circle(new_img, end1, r, c, thickness)
            cv2.circle(new_img, end2, r, c, thickness)

    tempfilename = tempfile.NamedTemporaryFile(prefix='matches_', suffix='.png', dir=os.path.dirname(im1), delete=False)
    tempfilename.close()

    #plt.show()
    #plt.savefig(tempfilename)
    #print(tempfilename.name)
    cv2.imwrite(tempfilename.name, new_img)
    return tempfilename.name


def get_tile_pair_matched_image(render, stack, tileId1, tileId2, pGroupId, qGroupId, outdir, matchCollectionOwner, matchCollection, renderScale=0.1):
    #img1 = renderapi.image.get_tile_image_data(stack, tileId1, scale=renderScale, render=render)
    #img2 = renderapi.image.get_tile_image_data(stack, tileId2, scale=renderScale, render=render)
    im1 = '%s.jpg'%(tileId1)
    im2 = '%s.jpg'%(tileId2)
    im1 = os.path.join(outdir, im1)
    im2 = os.path.join(outdir, im2)

    # check if the point match collection exists
    collections = renderapi.pointmatch.get_matchcollections(owner=matchCollectionOwner, 
                                                            render=render)
    ptmatches = []
    if (matchCollection in collections):
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

    match_img_filename = draw_matches(im1, im2, ptmatches, renderScale)
    return match_img_filename, ptmatch_count


def compute_point_matches(render, stack, tile1, tile2, pGroupId, qGroupId, output_dir, fillWithNoise, url_options, option_keys, options):
    # get canvas urls
    canvas_urls = get_canvas_url(render.DEFAULT_KWARGS, stack, tile1, tile2, url_options)

    argvs  = []
    #outdir = 'pmopt'
    collection_name = 'pms'
    renderScale = 0.1
    for param, value in zip(option_keys, options):
        if param == "renderScale":
            renderScale = value
        argvs += ['--%s'%(param), value]
        #outdir += "_%s_%s"%(param, str(value))
        collection_name += '_%s'%(str(value).replace('.', 'D'))

    #outdir = os.path.join(output_dir, outdir)
    outdir = output_dir


    baseDataUrl = renderapi.render.format_baseurl(render.DEFAULT_KWARGS['host'], render.DEFAULT_KWARGS['port'])
    argvs += ['--baseDataUrl', baseDataUrl]
    argvs += ['--owner', render.DEFAULT_KWARGS['owner']]
    argvs += ['--collection', collection_name]
    #argvs += ['--matchStorageFile', os.path.join(outdir, 'matches.json')]
    argvs += ['--debugDirectory', outdir]
    argvs += ['', canvas_urls]

    # run the point match client
    renderapi.client.call_run_ws_client('org.janelia.render.client.PointMatchClient',
                                        add_args=argvs,
                                        renderclient=render,
                                        memGB='2G')

    # create the image showing the matched features and add it to an html file
    match_img_filename, ptmatch_count = get_tile_pair_matched_image(render,
                                                    stack,
                                                    tile1,
                                                    tile2,
                                                    pGroupId,
                                                    qGroupId,
                                                    outdir,
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

    return_struct = {}
    return_struct['options'] = options
    return_struct['keys'] = option_keys
    return_struct['zipped'] = zip(option_keys, options)
    return_struct['match_img_filename'] = match_img_filename
    return_struct['ptmatch_count'] = ptmatch_count
    return_struct['tilepair_url'] = tilepair_base_url
    return_struct['outdir'] = outdir
    return return_struct


class PointMatchOptimizationModule(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = PointMatchOptimizationParameters
        super(PointMatchOptimizationModule, self).__init__(
            schema_type=schema_type, *args, **kwargs)

    def run(self):
        # create a stack with the two tiles
        ts1 = renderapi.tilespec.get_tile_spec(self.args['stack'], self.args['tileId1'], render=self.render)
        ts2 = renderapi.tilespec.get_tile_spec(self.args['stack'], self.args['tileId2'], render=self.render)
        ts = []
        ts.append(ts1)
        ts.append(ts2)

        pGroupId = ts1.layout.sectionId
        qGroupId = ts2.layout.sectionId

        # create the tile stack
        if self.args['tile_stack'] is None:
            tile_stack = "pmopt_{}_t{}".format(self.args['stack'],
                                                time.strftime("%m%d%y_%H%M%S"))
            self.args['tile_stack'] = tile_stack

        renderapi.stack.create_stack(self.args['tile_stack'], render=self.render)
        renderapi.client.import_tilespecs(self.args['tile_stack'], ts, render=self.render)
        renderapi.stack.set_stack_state(self.args['tile_stack'], 'COMPLETE', render=self.render)

        # the order of these two lines matter
        keys, options = get_parameter_sets_and_strings(self.args['SIFT_options'])
        mypartial = partial(compute_point_matches,
                            self.render,
                            self.args['tile_stack'],
                            self.args['tileId1'],
                            self.args['tileId2'],
                            pGroupId,
                            qGroupId,
                            self.args['outputDirectory'],
                            self.args['fillWithNoise'],
                            self.args['url_options'],
                            keys)

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            return_struct = pool.map(mypartial, options)

        #print(os.path.dirname(__file__))
        m = render_from_template(os.path.dirname(__file__), 'optimization.html', return_struct=return_struct)
        #print(m)
        tempfilename = tempfile.NamedTemporaryFile(prefix='match_html_', suffix='.html', dir=self.args['outputDirectory'], delete=False)
        tempfilename.close()
        ff = open(tempfilename.name, "w")
        ff.write(m)
        ff.close()
        self.output({"output_html": tempfilename.name})

if __name__=="__main__":
    mod = PointMatchOptimizationModule(input_data=ex)
    mod.run()
