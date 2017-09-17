if __name__ == "__main__" and __package__ is None:
    __package__ = "renderapps.intensity_correction.multIntensityCorr"
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

example_input = {
    "render": {
        "host": "ibs-forrestc-ux1",
        "port": 8080,
        "owner": "M246930_Scnn1a",
        "project": "M246930_Scnn1a_4",
        "client_scripts": "/var/www/render/render-ws-java-client/src/main/scripts"
    },
    "input_stack": "Acquisition_DAPI_1",
    "correction_stack": "Median_TEST_DAPI_1",
    "output_stack": "Flatfield_TEST_DAPI_1",
    "output_directory": "/nas/data/M246930_Scnn1a_4/processed/FlatfieldTEST",
    "z_index": 102,
    "pool_size": 20
}

class MultIntensityCorrParams(RenderParameters):
    input_stack = Str(required=True,
        metadata={'description':'Input stack'})
    output_stack = Str(required=True,
        metadata={'description':'Output stack'})
    correction_stack = Str(required=True,
        metadata={'description':'Correction stack (usually median stack for AT data)'})
    output_directory = Str(required=True,
        metadata={'description':'Directory for storing Images'})
    z_index = Int(required=True,
        metadata={'description':'z value for section'})
    pool_size = Int(required=False,default=20,description='size of pool for parallel processing (default=20)')

def intensity_corr(img,ff):
        img = img.astype(float)
        ff = ff.astype(float)

        num = np.ones((ff.shape[0],ff.shape[1]))
        fac = np.divide(num* np.amax(ff),ff+0.0001)
        result = np.multiply(img,fac)
        result = np.multiply(result,np.mean(img)/np.mean(result))
        result_int = np.uint16(result)
        return result_int

def getImage(ts):
    d = ts.to_dict()
    img0 = tifffile.imread(d['mipmapLevels'][0]['imageUrl'])
    (N,M)=img0.shape
    return N,M,img0

def process_tile(C,dirout, stackname,input_ts):

    [N,M,C] = getImage(input_ts)
    [N1,M1,I] = getImage(input_ts)
    Res = intensity_corr(I,C)
    if not os.path.exists(dirout):
        os.makedirs(dirout)
    d = input_ts.to_dict()
    [head,tail] = os.path.split(d['mipmapLevels'][0]['imageUrl'])
    outImage = "%s/%s_%04d_%s"%(dirout,stackname,input_ts.z,tail)
    tifffile.imsave(outImage,I)


    output_ts = input_ts
    d = output_ts.to_dict()
    for i in range(1,len(d['mipmapLevels'])):
        del d['mipmapLevels'][i]
    d['mipmapLevels'][0]['imageUrl'] = outImage
    output_ts.from_dict(d)
    return output_ts

class MultIntensityCorr(RenderModule):
    def __init__(self,schema_type=None,*args,**kwargs):
        if schema_type is None:
            schema_type = MultIntensityCorrParams
        super(MultIntensityCorr,self).__init__(schema_type=schema_type,*args,**kwargs)

    def run(self):

        #get tilespecs
        Z = self.args['z_index']
        inp_tilespecs = self.render.run(renderapi.tilespec.get_tile_specs_from_z,self.args['input_stack'],Z)
        corr_tilespecs = self.render.run(renderapi.tilespec.get_tile_specs_from_z,self.args['correction_stack'],Z)


        #mult intensity correct each tilespecs and return tilespecs
        render=self.render
        C = getImage(corr_tilespecs[0]);
        mypartial = partial(process_tile,C, self.args['output_directory'],self.args['output_stack'])
        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            tilespecs = pool.map(mypartial,inp_tilespecs)

        #upload to render
        renderapi.stack.create_stack(self.args['output_stack'],cycleNumber=2,cycleStepNumber=1,render=self.render)
        renderapi.client.import_tilespecs(self.args['output_stack'],tilespecs,render=self.render)
        renderapi.stack.set_stack_state(self.args['output_stack'],"COMPLETE",render=self.render)

if __name__ == "__main__":
    mod = MultIntensityCorr(input_data=example_input,schema_type=MultIntensityCorrParams)
    mod.run()
