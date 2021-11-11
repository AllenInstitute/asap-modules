import errno
from functools import partial
import glob
import os
import uuid

import numpy as np
import pathlib2 as pathlib
import renderapi

from rendermodules.utilities.pillow_utils import Image
from rendermodules.materialize.render_downsample_sections import (
    RenderSectionAtScale)
from rendermodules.dataimport.schemas import (
    MakeMontageScapeSectionStackParameters, MakeMontageScapeSectionStackOutput)
from rendermodules.module.render_module import (
    StackOutputModule, RenderModuleException)

example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8080,
        "owner": "gayathri",
        "project": "Tests",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_latest/render-ws-java-client/src/main/scripts"
    },
    "montage_stack": "rough_test_montage_stack",
    "output_stack": "rough_test_downsample_montage_stack",
    "image_directory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/scratch",
    "set_new_z": "False",
    "new_z_start": 1020,
    "remap_section_ids": False,
    "imgformat": "png",
    "scale": 0.1,
    "apply_scale": "False",
    "zstart": 1020,
    "zend": 1022,
    "pool_size": 20
}


def create_montage_scape_tile_specs(render, input_stack, image_directory,
                                    scale, project, tagstr, imgformat,
                                    Z, apply_scale=False, uuid_prefix=True,
                                    uuid_prefix_length=10,
                                    **kwargs):
    z = Z[0]
    newz = Z[1]

    # create the full path to the images
    # directory structure as per Render's RenderSectionClient output
    [q, r] = divmod(z, 1000)
    s = int(r / 100)

    filename = os.path.join(image_directory,
                            project,
                            input_stack,
                            'sections_at_%s' % str(scale),
                            '%03d' % q,
                            '%d' % s,
                            '%s.0.%s' % (str(z), imgformat))

    # This is really a slow way of generating the downsample sections
    # need to submit the job in a cluster
    if not os.path.isfile(filename):
        print("Montage scape does not exist for %d. Creating one now..." % z)
        tempstack = RenderSectionAtScale.downsample_specific_mipmapLevel(
            [z], input_stack, image_directory=image_directory,
            scale=scale, render=render, imgformat=imgformat, **kwargs)
        filename = os.path.join(image_directory,
                                project,
                                tempstack,
                                'sections_at_%s' % str(scale),
                                '%03d' % q,
                                '%d' % s,
                                '%s.0.%s' % (str(z), imgformat))

    # generate tilespec for this z
    tilespecs = render.run(renderapi.tilespec.get_tile_specs_from_z,
                           input_stack,
                           z)

    # generate tilespec for downsampled montage
    # tileId is the first tileId from source z
    t = tilespecs[0]

    if uuid_prefix:
        t.tileId = "ds{uid}_{tId}".format(
            uid=uuid.uuid4().hex[:uuid_prefix_length],
            tId=t.tileId)

    with Image.open(filename) as im:
        t.width, t.height = im.size
    t.ip[0] = renderapi.image_pyramid.MipMap(
        imageUrl=pathlib.Path(filename).as_uri())
    [t.ip.pop(k) for k in list(t.ip.keys()) if k != '0']
    t.minIntensity = 0
    t.maxIntensity = 255
    t.z = newz
    t.layout.sectionId = "%s.0" % str(int(newz))
    if apply_scale:
        t.tforms = [renderapi.transform.AffineModel(
            M00=(1./scale), M11=(1./scale))]
    else:
        t.tforms = [renderapi.transform.AffineModel(
            M00=(1.), M11=(1.))]

    allts = [t]

    tilespecfilename = os.path.join(image_directory,
                                    project,
                                    input_stack,
                                    'sections_at_%s' % str(scale),
                                    'tilespecs_%s' % tagstr,
                                    'tilespec_%04d.json' % z)

    with open(tilespecfilename, 'w') as fp:
        renderapi.utils.renderdump(allts, fp, indent=4)


class MakeMontageScapeSectionStack(StackOutputModule):
    default_schema = MakeMontageScapeSectionStackParameters
    default_output_schema = MakeMontageScapeSectionStackOutput

    def run(self):
        self.logger.debug('Montage scape stack generation module')

        # get the list of z indices
        zvalues = self.render.run(
            renderapi.stack.get_z_values_for_stack,
            self.args['montage_stack'])
        zvalues1 = self.zValues
        zvalues = list(set(zvalues1).intersection(set(zvalues)))

        if not zvalues:
            raise RenderModuleException(
                'No sections found for stack {}'.format(
                    self.args['montage_stack']))

        # generate tuple of old and new Zs
        # setting a new z range does not check whether the range
        #   overlaps with existing sections/chunks in the output stack
        if self.args['set_new_z']:
            zvalues = list(np.sort(np.array(zvalues)))
            diffarray = [x-zvalues[0] for x in zvalues]
            newzvalues = [self.args['new_z_start'] + x for x in diffarray]
        else:
            newzvalues = zvalues

        Z = [[int(oldz), int(newz)] for oldz, newz in zip(zvalues, newzvalues)]

        out_stack_exists = self.args['output_stack'] in self.render.run(
            renderapi.render.get_stacks_by_owner_project)

        if out_stack_exists:
            # check whether overwrite z is set to false. If so, then remove those z that is already in output stack
            outzvalues = renderapi.stack.get_z_values_for_stack(
                            self.args['output_stack'],
                            render=self.render)

            if self.overwrite_zlayer:
                # stack has to be in loading state
                renderapi.stack.set_stack_state(self.args['output_stack'],
                                                'LOADING',
                                                render=self.render)
                for oldz, newz in zip(zvalues, newzvalues):
                    # delete the section from output stack
                    renderapi.stack.delete_section(self.args['output_stack'],
                                                   newz,
                                                   render=self.render)

        # generate the tag string to add to output tilespec json file name
        tagstr = "%s_%s" % (min(zvalues), max(zvalues))

        tilespecdir = os.path.join(self.args['image_directory'],
                                   self.args['render']['project'],
                                   self.args['montage_stack'],
                                   'sections_at_%s'%str(self.args['scale']),
                                   'tilespecs_%s'%tagstr)

        try:
            os.makedirs(tilespecdir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
            pass

        render_materialize = renderapi.connect(
            **self.render.make_kwargs(memGB=self.args['memGB_materialize']))
        # process for each z
        mypartial = partial(
            create_montage_scape_tile_specs,
            render_materialize,
            self.args['montage_stack'],
            self.args['image_directory'],
            self.args['scale'],
            self.args['render']['project'],
            tagstr,
            self.args['imgformat'],
            apply_scale=self.args['apply_scale'],
            level=self.args['level'],
            pool_size=1,
            doFilter=self.args['doFilter'],
            fillWithNoise=self.args['fillWithNoise'],
            uuid_prefix=self.args["uuid_prefix"],
            uuid_prefix_length=self.args["uuid_length"],
            do_mp=False)

        with renderapi.client.WithPool(
                self.args['pool_size_materialize']) as pool:
            pool.map(mypartial, Z)

        # get all the output tilespec json files
        tspath = os.path.join(self.args['image_directory'],
                              self.args['render']['project'],
                              self.args['montage_stack'],
                              'sections_at_%s' % str(self.args['scale']),
                              'tilespecs_%s' % tagstr)

        jsonfiles = glob.glob("%s/*.json" % tspath)

        if not jsonfiles:
            raise RenderModuleException('No tilespecs json files were generated')

        # create the stack if it doesn't exist
        if self.output_stack not in self.render.run(
                renderapi.render.get_stacks_by_owner_project):
            # stack does not exist
            # TODO configurable stack metadata
            self.render.run(renderapi.stack.create_stack,
                            self.output_stack,
                            cycleNumber=5,
                            cycleStepNumber=1,
                            stackResolutionX=1,
                            stackResolutionY=1)

        # import tilespecs to render
        self.render.run(renderapi.client.import_jsonfiles_parallel,
                        self.output_stack,
                        jsonfiles)

        if self.close_stack:
            # set stack state to complete
            self.render.run(renderapi.stack.set_stack_state,
                            self.output_stack,
                            state='COMPLETE')

        self.output({'output_stack': self.output_stack})


if __name__ == "__main__":
    mod = MakeMontageScapeSectionStack()
    mod.run()
