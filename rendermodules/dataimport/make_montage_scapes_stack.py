from functools import partial
import glob
import os
import json
from PIL import Image
import renderapi
from rendermodules.dataimport.schemas import MakeMontageScapeSectionStackParameters, MakeMontageScapeSectionStackOutput
from ..module.render_module import RenderModule, RenderModuleException



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
    "set_new_z":"False",
    "new_z_start": 1020,
    "imgformat":"png",
    "scale": 0.1,
    "zstart": 1020,
    "zend": 1022,
    "pool_size": 20
}

'''
example = {
    "render": {
        "owner": "1_ribbon_expts",
        "project": "M335503_RIC4_Ai139_LRW",
        "host": "ibs-forrestc-ux1",
        "port": 8080,
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "montage_stack": "Stitched_2_DAPI_2_dropped",
    "output_stack": "TESTGAYATHRI_DownsampledDAPI",
    "image_directory":"/nas/module_test",
    "set_new_z":"True",
    "new_z_start": 10,
    "pool_size": 20,
    "scale": 0.05,
    "zstart": 0,
    "zend": 15
}
'''

def create_montage_scape_tile_specs(render, input_stack, image_directory, scale, project, tagstr, imgformat, Z):

    z = Z[0]
    newz = Z[1]

    # create the full path to the images
    # directory structure as per Render's RenderSectionClient output
    [q,r] = divmod(z,1000)
    s = int(r/100)

    filename = os.path.join(image_directory,
                            project,
                            input_stack,
                            'sections_at_%s'%str(scale),
                            '%03d'%q,
                            '%d'%s,
                            '%s.0.%s'%(str(z),imgformat))

    # get stack bounds to set the image width and height
    #stackbounds = render.run(
    #                renderapi.stack.get_stack_bounds,
    #                input_stack)


    # This is really a slow way of generating the downsample sections
    # need to submit the job in a cluster
    if not os.path.isfile(filename):
        print "Montage scape does not exist for %d. Creating one now..."%z
        render.run(renderapi.client.renderSectionClient, 
                   input_stack, 
                   image_directory, 
                   [z], 
                   scale=str(scale), 
                   format=imgformat, 
                   doFilter=True, 
                   fillWithNoise=False)

    # get section bounds
    sectionbounds = render.run(renderapi.stack.get_bounds_from_z,
                               input_stack,
                               z)

    stackbounds = render.run(renderapi.stack.get_stack_bounds,
                             input_stack)

    # generate tilespec for this z
    tilespecs = render.run(renderapi.tilespec.get_tile_specs_from_z,
                           input_stack,
                           z)

    t = tilespecs[0]
    d = t.to_dict()

    # EM_aligner expects the level 0 to be filled regardless of other level mipmaps
    d['mipmapLevels'][0] = {}
    d['mipmapLevels'][0]['imageUrl'] = filename

    # remove all the mipmap levels that will disrupt the NDViz viewing
    [d['mipmapLevels'].pop(k) for k in list(d['mipmapLevels'].keys()) if k != 0]
    d['minIntensity'] = 0
    d['maxIntensity'] = 255
    d['minX'] = sectionbounds['minX']/scale
    d['minY'] = sectionbounds['minY']/scale
    d['maxX'] = sectionbounds['maxX']/scale
    d['maxY'] = sectionbounds['maxY']/scale
    im = Image.open(filename)
    d['width'] = im.size[0]
    d['height'] = im.size[1]

    # the scale is required by the AT team to view the downsampled section overlayed with the montage section
    # this scale is to be accounted later in the apply_rough_alignment_transform_to_montage script
    #d['width'] = stackbounds['maxX']/scale
    #d['height'] = stackbounds['maxY']/scale
    d['z'] = newz
    v0 = 1.0 / scale
    v1 = 0.0
    v2 = 0.0
    v3 = 1.0 / scale
    v4 = 0.0
    v5 = 0.0
    #d['transforms']['specList'][-1]['dataString'] = "1.0000000000 0.0000000000 0.0000000000 1.0000000000 %d %d"%(0.0, 0.0)
    d['transforms']['specList'][-1]['dataString'] = "%f %f %f %f %s %s"%(v0, v1, v2, v3, v4, v5)

    # if there is a lens correction transformation in the tilespecs remove that
    if len(d['transforms']['specList']) > 1:
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




class MakeMontageScapeSectionStack(RenderModule):
    default_schema = MakeMontageScapeSectionStackParameters
    default_output_schema = MakeMontageScapeSectionStackOutput
    
    def run(self):
        self.logger.debug('Montage scape stack generation module')

        # get the list of z indices
        zvalues = self.render.run(
            renderapi.stack.get_z_values_for_stack,
            self.args['montage_stack'])
        zvalues1 = range(self.args['zstart'], self.args['zend']+1)
        zvalues = list(set(zvalues1).intersection(set(zvalues)))

        if not zvalues:
            raise RenderModuleException('No sections found for stack {}'.format(self.args['montage_stack']))

        # generate tuple of old and new Zs
        # setting a new z range does not check whether the range overlaps with existing sections/chunks in the output stack
        if self.args['set_new_z']:
            newzvalues = range(self.args['new_z_start'], self.args['new_z_start']+len(zvalues))
        else:
            newzvalues = zvalues

        Z = [[int(oldz),int(newz)] for oldz, newz in zip(zvalues, newzvalues)]


        # generate the tag string to add to output tilespec json file name
        tagstr = "%s_%s" % (min(zvalues), max(zvalues))

        # only applicable to AT team
        #f = open(self.args['num_sections_file'], 'w')
        #f.write("%d"%len(zvalues))
        #f.close()

        tilespecdir = os.path.join(self.args['image_directory'], 
                                   self.args['render']['project'], 
                                   self.args['montage_stack'], 
                                   'sections_at_%s'%str(self.args['scale']), 
                                   'tilespecs_%s'%tagstr)
        
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
        tspath = os.path.join(self.args['image_directory'],
                         self.args['render']['project'],
                         self.args['montage_stack'],
                         'sections_at_%s'%str(self.args['scale']),
                         'tilespecs_%s'%tagstr)

        jsonfiles = glob.glob("%s/*.json"%tspath)

        if not jsonfiles:
            raise RenderModuleException('No tilespecs json files were generated')

        # create the stack if it doesn't exist
        if self.args['output_stack'] not in self.render.run(renderapi.render.get_stacks_by_owner_project):
            # stack does not exist
            self.render.run(renderapi.stack.create_stack,
                            self.args['output_stack'],
                            cycleNumber=5,
                            cycleStepNumber=1,
                            stackResolutionX = 1,
                            stackResolutionY = 1)

        # import tilespecs to render
        self.render.run(renderapi.client.import_jsonfiles_parallel,
                        self.args['output_stack'],
                        jsonfiles)

        # set stack state to complete
        self.render.run(renderapi.stack.set_stack_state,
                        self.args['output_stack'],
                        state='COMPLETE')

        self.output({'output_stack': self.args['output_stack']})


if __name__ == "__main__":
    mod = MakeMontageScapeSectionStack(input_data=example)
    mod.run()