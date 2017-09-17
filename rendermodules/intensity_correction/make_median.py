if __name__ == "__main__" and __package__ is None:
    __package__ = "renderapps.intensity_correction.make_median"
import json
import os
import renderapi
from ..module.render_module import RenderModule, RenderParameters
from argschema.fields import InputFile, InputDir, Str, Float, Int
from functools import partial
import glob
import time
import numpy as np
import time
from PIL import Image
import tifffile
from scipy.ndimage.filters import gaussian_filter


example_input = {
    "render": {
        "host": "ibs-forrestc-ux1",
        "port": 8080,
        "owner": "M246930_Scnn1a",
        "project": "M246930_Scnn1a_4",
        "client_scripts": "/var/www/render/render-ws-java-client/src/main/scripts"
    },
    "input_stack": "Acquisition_DAPI_1",
    "file_prefix": "Median",
    "output_stack": "Median_TEST_DAPI_1",
    "output_directory": "/nas/data/M246930_Scnn1a_4/processed/Medians",
    "minZ": 100,
    "maxZ": 103,
    "pool_size": 20
}

class MakeMedianParams(RenderParameters):
    input_stack = Str(required=True,
        metadata={'description':'Input stack'})
    file_prefix = Str(required=False,default="Median",
        metadata={'description':'File prefix for median image file that is saved'})
    output_directory = Str(required=True,
        metadata={'description':'Output Directory for saving median image'})
    output_stack = Str(required=True,
        metadata={'description':'Output stack'})
    minZ = Int(required=True,
        metadata={'description':'z value for section'})
    maxZ = Int(required=True,
        metadata={'description':'z value for section'})
    pool_size = Int(required=False,default=20,description='size of pool for parallel processing (default=20)')

def getImage(ts):
    d = ts.to_dict()
    img0 = tifffile.imread(d['mipmapLevels'][0]['imageUrl'])
    (N,M)=img0.shape
    return N,M,img0

def getImageFromTilespecs(alltilespecs,index):
    N,M,img = getImage(alltilespecs[index])
    return img

class MakeMedian(RenderModule):
    def __init__(self,schema_type=None,*args,**kwargs):
        if schema_type is None:
            schema_type = MakeMedianParams
        super(MakeMedian,self).__init__(schema_type=schema_type,*args,**kwargs)

    def run(self):

        #inits
        alltilespecs = []
        numtiles = 0
        firstts = []
        render=self.render
        outtilespecs = []
        ind = 0

        #get tilespecs for z

        for z in range(self.args['minZ'],self.args['maxZ']):
            tilespecs = self.render.run(renderapi.tilespec.get_tile_specs_from_z,self.args['input_stack'],z)
            alltilespecs.extend(tilespecs)
            firstts.append(tilespecs[0]) #used for easy creation of tilespecs for output stack
            numtiles += len(tilespecs)

        #read images and create stack
        N,M,img0 = getImage(alltilespecs[0])
        stack = np.zeros((N,M,numtiles),dtype=img0.dtype)
        mypartial = partial(getImageFromTilespecs,alltilespecs)
        indexes = range(0,numtiles)
        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            images = pool.map(mypartial,indexes)

        #calculate median
        for i in range(0,len(images)):
            stack[:,:,i] = images[i]
        np.median(stack,axis=2,overwrite_input=True)
        (A,B,C)=stack.shape
        if (numtiles%2 == 0):
            med1 = stack[:,:,numtiles/2-1]
            med2 = stack[:,:,numtiles/2+1]
            med = (med1+med2)/2
        else:
            med = stack[:,:,(numtiles-1)/2]
        med = gaussian_filter(med,10)

        #save image and create output tilespecs
        outdir = self.args['output_directory']
        if not os.path.exists(outdir):
			os.makedirs(outdir)

        for z in range(self.args['minZ'],self.args['maxZ']):
            outImage = outdir + "/%s_%s_%d.tif"%(self.args['file_prefix'],self.args['output_stack'], z)
            tifffile.imsave(outImage,med)
            ts = firstts[ind]
            ts.z = z
            d = ts.to_dict()
            d['mipmapLevels'][0]['imageUrl'] = outImage
            ts.from_dict(d)
            outtilespecs.append(ts)
            ind += 1

        #upload to render
        renderapi.stack.create_stack(self.args['output_stack'],cycleNumber=2,cycleStepNumber=1,render=self.render)
        renderapi.stack.set_stack_state(self.args['output_stack'],"LOADING",render=self.render)
        renderapi.client.import_tilespecs(self.args['output_stack'],outtilespecs,render=self.render)
        renderapi.stack.set_stack_state(self.args['output_stack'],"COMPLETE",render=self.render)

if __name__ == "__main__":
    mod = MakeMedian(input_data=example_input,schema_type=MakeMedianParams)
    mod.run()
