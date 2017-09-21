
import os
import json
import renderapi
import glob
import numpy as np
from argschema import InputFile, InputDir
import marshmallow as mm
from ..module.render_module import RenderModule, RenderParameters
from functools import partial

if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.rough_align.apply_rough_alignment_transform_to_montage_stack"

example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8998,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    "montage_stack": "mm2_acquire_8bit_reimage_clone",
    "prealigned_stack": "mm2_acquire_8bit_reimage_clone",
    "lowres_stack": "mm2_8bit_reimage_minimaps",
    "output_stack": "mm2_8bit_reimage_raw_rough_aligned",
    "tilespec_directory": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/scratch/rough/jsonFiles",
    "set_new_z": "False",
    "minZ": 1015,
    "maxZ": 1015,
    "scale": 0.025,
    "pool_size": 10
}


def apply_rough_alignment(render, input_stack, prealigned_stack, lowres_stack, output_dir, scale, Z):
    z = Z[0]
    newz = Z[1]

    try:
        print z
        print "A"
        # get lowres stack tile specs
        lowres_ts = render.run(
                            renderapi.tilespec.get_tile_specs_from_z,
                            lowres_stack,
                            newz)

        # get input stack tile specs (for the first tile)
        highres_ts = render.run(
                            renderapi.tilespec.get_tile_specs_from_z,
                            input_stack,
                            z)[0]

        # get the section bounding box
        sectionbounds = render.run(
                            renderapi.stack.get_bounds_from_z,
                            prealigned_stack,
                            z)

        # get the lowres stack rough alignment transformation
        tforms = lowres_ts[0].tforms
        print "B"
        d = tforms[-1].to_dict()
        dsList = d['dataString'].split()
        v0 = float(dsList[0])*scale
        v1 = float(dsList[1])*scale
        v2 = float(dsList[2])*scale
        v3 = float(dsList[3])*scale
        v4 = float(dsList[4])
        v5 = float(dsList[5])
        d['dataString'] = "%f %f %f %f %s %s"%(v0, v1, v2, v3, v4, v5)
        tforms[-1].from_dict(d)
        print "C"
        stackbounds = render.run(
                            renderapi.stack.get_bounds_from_z,
                            input_stack,
                            z)
        prestackbounds = render.run(
                            renderapi.stack.get_bounds_from_z,
                            prealigned_stack,
                            z)
        tx =  int(stackbounds['minX']) - int(prestackbounds['minX'])
        ty =  int(stackbounds['minY']) - int(prestackbounds['minY'])
        print "D"
        tforms1 = highres_ts.tforms
        d = tforms1[-1].to_dict()
        print d
        dsList = d['dataString'].split()
        v0 = 1.0
        v1 = 0.0
        v2 = 0.0
        v3 = 1.0
        v4 = tx
        v5 = ty
        d['dataString'] = "%f %f %f %f %s %s"%(v0,v1,v2,v3,v4,v5)
        tforms1[-1].from_dict(d)
        print "E"

        print tforms1
        print tforms

        ftform = tforms1 + tforms
        print ftform
        print "F"
        allts = []
        highres_ts1 = render.run(
                            renderapi.tilespec.get_tile_specs_from_z,
                            input_stack,
                            z)
        for t in highres_ts1:
            #print "f1"
            t.tforms.append(ftform)
            #print "f2"
            d1 = t.to_dict()
            #print "f3"
            #print d1['mipmapLevels'][0]['imageUrl']
            d1['z'] = newz
            t.from_dict(d1)
            allts.append(t)

        print "G"
        tilespecfilename = os.path.join(output_dir,'tilespec_%04d.json'%newz)
        print tilespecfilename
        fp = open(tilespecfilename,'w')
        json.dump([ts.to_dict() for ts in allts] ,fp,indent=4)
        fp.close()
    except:
        print "This z has not been aligned!"





class ApplyRoughAlignmentTransformParameters(RenderParameters):
    montage_stack = mm.fields.Str(
        required=True,
        metadata={'description':'stack to make a downsample version of'})
    prealigned_stack = mm.fields.Str(
        required=False,default=montage_stack,
        metadata={'description':'stack with dropped tiles corrected for stitching errors'})
    lowres_stack = mm.fields.Str(
        required=True,
        metadata={'description':'montage scape stack with rough aligned transform'})
    output_stack = mm.fields.Str(
        required=True,
        metadata={'description':'output high resolution rough aligned stack'})
    tilespec_directory = mm.fields.Str(
        required=True,
        metadata={'description':'path to save section images'})
    set_new_z = mm.fields.Boolean(
        required=False,
        metadata={'description':'set to assign new z values starting from 0 (default - False)'})
    scale = mm.fields.Float(
        required=True,
        metadata={'description':'scale of montage scapes'})
    pool_size = mm.fields.Int(
        require=False,
        default=5,
        metadata={'description':'pool size for parallel processing'})
    minZ = mm.fields.Int(
        required=True,
        metadata={'description':'Minimum Z value'})
    maxZ = mm.fields.Int(
        required=True,
        metadata={'description':'Maximum Z value'})


class ApplyRoughAlignmentTransform(RenderModule):
    def __init__(self, schema_type=None, *args, **kwargs):
        if schema_type is None:
            schema_type = ApplyRoughAlignmentTransformParameters
        super(ApplyRoughAlignmentTransform, self).__init__(
            schema_type=schema_type, *args, **kwargs)


    def run(self):
        allzvalues = self.render.run(
            renderapi.stack.get_z_values_for_stack,
            self.args['montage_stack'])
        allzvalues = np.array(allzvalues)
        zvalues = allzvalues[(allzvalues >= self.args['minZ']) & (allzvalues <= self.args['maxZ'])]

        if self.args['set_new_z']:
            newzvalues = range(0, len(zvalues))
        else:
            newzvalues = zvalues

        # the old and new z values are required for the AT team
        Z = [[a,b] for a,b in zip(zvalues, newzvalues)]

        mypartial = partial(
                        apply_rough_alignment,
                        self.render,
                        self.args['montage_stack'],
                        self.args['prealigned_stack'],
                        self.args['lowres_stack'],
                        self.args['tilespec_directory'],
                        self.args['scale'])

        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            pool.map(mypartial, Z)

        jsonfiles = glob.glob("%s/*.json"%self.args['tilespec_directory'])
        # Create the output stack if it doesn't exist
        if self.args['output_stack'] not in self.render.run(renderapi.render.get_stacks_by_owner_project):
            # stack does not exist
            self.render.run(
                renderapi.stack.create_stack,
                self.args['output_stack'])

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
    mod = ApplyRoughAlignmentTransform(input_data=example)
    #mod = ApplyRoughAlignmentTransform(schema_type=ApplyRoughAlignmentTransformParameters)
    mod.run()
