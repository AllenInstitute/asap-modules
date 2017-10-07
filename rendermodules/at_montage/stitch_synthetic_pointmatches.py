import renderapi
import os
from functools import partial
import numpy as np
import subprocess
from rendermodules.module.render_module import RenderParameters
import json
from shapely.geometry import box, Polygon
import shapely
import time

example_parameters={
    "render":{
        "host":"ibs-forrestc-ux1",
        "port":8080,
        "owner":"S3_Run1",
        "project":"S3_Run1_Jarvis",
        "client_scripts":"/var/www/render/render-ws-java-client/src/main/scripts"
    },
    "stack":"BIGLENS_REG_MARCH_21_DAPI_1_deconvnew",
    "matchCollection":"M247514_Rorb_1_BIGLENS_REG_MARCH_21_DAPI_1_deconvnew_stitching",
    "minZ":0,
    "maxZ":101,
    "delta":200,
    "dataRoot":"/nas3/data/"
}

def make_tile_pair_json(r,json_dir,z):
    tile_json_pair_path=os.path.join(json_dir,'in_section_pairs_%s_z%04d.json'%(stack,z))
    renderapi.client.tilePairClient(stack,
                                minZ=z,
                                maxZ=z,
                                outjson=tile_json_pair_path,
                                xyNeighborFactor=.5,
                                zNeighborDistance=0,
                                render=r)
    return tile_json_pair_path

def get_world_box(ts):
    qcorners = np.array([[0,0],[0,ts.height],[ts.width,ts.height],[ts.width,0],[0,0]])
    world_corners=r.run(renderapi.coordinate.local_to_world_coordinates_array,stack,qcorners,ts.tileId,ts.z)
    return Polygon(world_corners)

def process_tile_pair_json_file(r,matchcollection,stack,owner,tile_pair_json_file,logger,delta=150):

    tile_pair_json = json.load(open(tile_pair_json_file,'r'))['neighborPairs']
    pairs = []

    for pair in tile_pair_json:
        now = time.time()

        qid = pair['q']['id']
        pid = pair['p']['id']
        qts = r.run(renderapi.tilespec.get_tile_spec,stack,qid)
        pts = r.run(renderapi.tilespec.get_tile_spec,stack,pid)

        polyq=get_world_box(qts)
        polyp=get_world_box(pts)

        poly_int = polyp.intersection(polyq)
        poly_int=poly_int.buffer(-10)
        if not poly_int.is_empty:
            minx,miny,maxx,maxy = poly_int.bounds
            xx,yy = np.meshgrid(np.arange(minx,maxx,delta),np.arange(miny,maxy,delta))
            xx=xx.ravel()
            yy=yy.ravel()
            isin = np.zeros(len(xx),np.bool)
            for i,xytuple in enumerate(zip(xx,yy)):
                x,y = xytuple
                p = shapely.geometry.Point(x,y)
                if poly_int.contains(p):
                    isin[i]=True
                else:
                    isin[i]=False
            xx=xx[isin]
            yy=yy[isin]
            #print 'step2', time.time()-now
            #now = time.time()
            xy = np.stack([xx,yy]).T
            if xy.shape[0]>0:
                int_local_q=renderapi.coordinate.world_to_local_coordinates_array(stack,xy,qts.tileId,qts.z,render=r)
                int_local_p=renderapi.coordinate.world_to_local_coordinates_array(stack,xy,pts.tileId,pts.z,render=r)

                newpair = {}
                newpair['pId']=pid
                newpair['qId']=qid
                newpair['pGroupId']=pair['p']['groupId']
                newpair['qGroupId']=pair['q']['groupId']
                newpair['matches']={}
                newpair['matches']['p']=[int_local_p[:,0].tolist(),int_local_p[:,1].tolist()]
                newpair['matches']['q']=[int_local_q[:,0].tolist(),int_local_q[:,1].tolist()]
                newpair['matches']['w']=np.ones(len(xx)).tolist()
                pairs.append(newpair)
    resp=r.run(renderapi.pointmatch.import_matches,matchcollection,json.dumps(pairs))

class CreateMontagePointMatch(RenderModule):
    default_schema = CreateMontagePointMatchParameters

    def run(self):
        self.logger.debug(mod.args)

        stack = self.args['stack']
        json_dir = os.path.join(self.args['dataRoot'],
            '%s/processed/point_match_in_place'%self.args['render']['project'])

        if not os.path.isdir(json_dir):
            os.makedirs(json_dir)

        #figure out what z values to visit
        zvalues = self.render.run(renderapi.stack.get_z_values_for_stack,stack)
        minZ = self.args.get('minZ',np.min(zvalues))
        maxZ = self.args.get('maxZ',np.max(zvalues))
        zvalues = np.array(zvalues)
        zvalues = zvalues[zvalues>minZ]
        zvalues = zvalues[zvalues<maxZ]

        make_tile_part = partial(make_tile_pair_json,self.render,json_dir)
        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            tile_pair_jsons=pool.map(make_tile_part,zvalues)

        myp = partial(process_tile_pair_json_file,
            self.render,
            self.args['matchCollection'],
            self.args['stack'],
            self.args['render']['owner'],
            delta=self.args['delta'])
        with renderapi.client.WithPool(self.args['pool_size']) as pool:
            res=pool.map(myp,tile_pair_jsons)

if __name__ == "__main__":
    mod = CreateMontagePointMatch(input_data = example_parameters)
    mod.run()
