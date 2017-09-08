import json
import os
import renderapi
from ..module.render_module import RenderModule, RenderParameters
import argschema
import marshmallow as mm
from functools import partial
import numpy as np
import time
from PIL import Image
import glob


if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.dataimport.make_montage_scapes_stack"


example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8998,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "montage_stack": "mm2_acquire_8bit_Montage",
    "output_stack": "mm2_montage_scape_test",
    "image_directory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch",
    "num_sections_file": "file.txt",
    "set_new_z":"False",
    "imgformat":"png",
    "scale": 0.05,
    "zstart": 1015,
    "zend": 1015,
    "pool_size": 20
}


def create_montage_scape_tile_specs(render, input_stack, image_directory, scale, project, tagstr, imgformat, Z):

    z = Z[0]
    newz = Z[1]

    print z

    # create tilespecdir path
    #tilespecdir = os.path.join(image_directory, project, input_stack, 'sections_at_%s'%str(scale), 'tilespecs_%s'%tagstr)
    #if not os.path.exists(tilespecdir):
    #    os.makedirs(tilespecdir)

    # create the full path to the images
    # directory structure as per Render's RenderSectionClient output
    [q,r] = divmod(z,1000)
    s = int(r/100)

    #directory = os.path.join(image_directory, stack, "sections_at_%s"%str(scale), "%03d"%q, "%d"%s)
    filename = os.path.join(image_directory,
                            project,
                            input_stack,
                            'sections_at_%s'%str(scale),
                            '%03d'%q,
                            '%d'%s,
                            '%s.0.%s'%(str(z),imgformat))

    #print filename
    if not os.path.isfile(filename):
        print "Montage scape does not exist for %d. Creating one now..."%z
        render.run(renderapi.client.renderSectionClient, input_stack, image_directory, [z], scale=str(scale), format=imgformat, doFilter=True, fillWithNoise=False)

    # get section bounds
    sectionbounds = render.run(
                        renderapi.stack.get_bounds_from_z,
                        input_stack,
                        z)

    # get stack bounds to set the image width and height
    stackbounds = render.run(
                    renderapi.stack.get_stack_bounds,
                    input_stack)

    # generate tilespec for this z
    tilespecs = render.run(
                    renderapi.tilespec.get_tile_specs_from_z,
                    input_stack,
                    z)

    t = tilespecs[0]
    d = t.to_dict()

    d['mipmapLevels'][0]['imageUrl'] = filename
    d['minIntensity'] = 0
    d['maxIntensity'] = 255
    #d['minX'] = sectionbounds['minX']*scale
    #d['minY'] = sectionbounds['minY']*scale
    #d['maxX'] = sectionbounds['maxX']*scale
    #d['maxY'] = sectionbounds['maxY']*scale
    #im = Image.open(filename)
    #d['width'] = im.size[0]
    #d['height'] = im.size[1]

    # the scale is required by the AT team to view the downsampled section overlayed with the montage section
    # this scale is to be accounted later in the apply_rough_alignment_transform_to_montage script
    d['width'] = stackbounds['maxX']*scale
    d['height'] = stackbounds['maxY']*scale
    d['z'] = newz
    v0 = 1.0 / scale
    v1 = 0.0
    v2 = 0.0
    v3 = 1.0 / scale
    v4 = 0.0
    v5 = 0.0
    #d['transforms']['specList'][-1]['dataString'] = "1.0000000000 0.0000000000 0.0000000000 1.0000000000 %d %d"%(0.0, 0.0)
    d['transforms']['specList'][-1]['dataString'] = "%f %f %f %f %s %s"%(v0, v1, v2, v3, v4, v5)
    d['transforms']['specList'].pop(0)
    t.from_dict(d)
    allts = [t]

    tilespecfilename = os.path.join(image_directory,
                                    project,
                                    input_stack,
                                    'sections_at_%s'%str(scale),
                                    'tilespecs_%s'%tagstr,
                                    'tilespec_%04d.json'%z)
    fp = open(tilespecfilename, 'w')
    json.dump([ts.to_dict() for ts in allts], fp, indent=4)
    fp.close()



class MakeMontageScapeSectionStackParameters(RenderParameters):
    montage_stack = mm.fields.Str(
        required=True,
        metadata={'description':'stack to make a downsample version of'})
    output_stack = mm.fields.Str(
        required=True,
        metadata={'description':'output stack name'})
    image_directory = argschema.InputDir(
        required=True,
        metadata={'description':'directory that stores the montage scapes'})
    num_sections_file = mm.fields.Str(
        required=True,
        metadata={'decription','file to save length of sections'})
    set_new_z = mm.fields.Boolean(
        required=False,
        metadata={'description':'set to assign new z values starting from 0 (default - False)'})
    imgformat = mm.fields.Str(
        required=False,
        default='tif',
        metadata={'description':'image format of the montage scapes (default - tif)'})
    scale = mm.fields.Float(
        required=True,
        metadata={'description':'scale of montage scapes'})
    zstart = mm.fields.Int(
        required=True,
        metadata={'description':'min z value'})
    zend = mm.fields.Int(
        required=True,
        metadata={'description':'max z value'})
    pool_size = mm.fields.Int(
        require=False,
        default=5,
        metadata={'description':'pool size for parallel processing'})


class MakeMontageScapeSectionStack(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = MakeMontageScapeSectionStackParameters
        super(MakeMontageScapeSectionStack, self).__init__(
            schema_type=schema_type, *args, **kwargs)

    def run(self):
        self.logger.debug('Montage scape stack generation module')

        # get the list of z indices
        zvalues = self.render.run(
            renderapi.stack.get_z_values_for_stack, self.args['montage_stack'])
        zvalues1 = range(self.args['zstart'], self.args['zend']+1)
        zvalues = list(set(zvalues1).intersection(set(zvalues)))

        if len(zvalues) == 0:
            self.logger.error('No sections found for stack {}'.format(
                self.args['montage_stack']))

        # generate tuple of old and new Zs
        if self.args['set_new_z']:
            newzvalues = range(0, len(zvalues))
        else:
            newzvalues = zvalues

        Z = [[oldz,newz] for oldz, newz in zip(zvalues, newzvalues)]


        # generate the tag string to add to output tilespec json file name
        tagstr = "%s_%s" % (min(zvalues), max(zvalues))

        # only applicable to AT team
        f = open(self.args['num_sections_file'], 'w')
        f.write("%d"%len(zvalues))
        f.close()

        tilespecdir = os.path.join(self.args['image_directory'], self.args['render']['project'], self.args['montage_stack'], 'sections_at_%s'%str(self.args['scale']), 'tilespecs_%s'%tagstr)
        if not os.path.exists(tilespecdir):
            os.makedirs(tilespecdir)

        # process for each z
        mypartial = partial(
            create_montage_scape_tile_specs,
            self.render,
            self.args['montage_stack'],
            self.args['image_directory'],
            self.args['scale'],
            self.args['render']['project'],
            tagstr,
            self.args['imgformat'])

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            pool.map(mypartial, Z)

        # get all the output tilespec json files
        t = os.path.join(self.args['image_directory'],
                         self.args['render']['project'],
                         self.args['montage_stack'],
                         'sections_at_%s'%str(self.args['scale']),
                         'tilespecs_%s'%tagstr)
        jsonfiles = glob.glob("%s/*.json"%t)

        #print jsonfiles
        # create the stack if it doesn't exist
        if self.args['output_stack'] not in self.render.run(renderapi.render.get_stacks_by_owner_project):
            # stack does not exist
            self.render.run(
                renderapi.stack.create_stack,
                self.args['output_stack'],
                cycleNumber=5,
                cycleStepNumber=1,
                stackResolutionX = 1,
                stackResolutionY = 1)

        # import tilespecs to render
        self.render.run(
            renderapi.client.import_jsonfiles_parallel,
            self.args['output_stack'],
            jsonfiles)

        # set stack state to complete
        self.render.run(
            renderapi.stack.set_stack_state,
            self.args['output_stack'],
            state='COMPLETE')


if __name__ == "__main__":
    mod = MakeMontageScapeSectionStack(input_data=example)
    #mod = MakeMontageScapeSectionStack(schema_type=MakeMontageScapeSectionStackParameters)

    mod.run()
