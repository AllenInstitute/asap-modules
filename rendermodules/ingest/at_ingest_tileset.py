# Adapted from ingest_tileset

if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.ingest.at_ingest_tileset"

import os
import re
import json
import datetime
import pytz
import argschema
from marshmallow import ValidationError
from schemas import ATIngestTileSetParams
import requests

example_input= {
        'inputdir': '/allen/programs/celltypes/production/incoming/shotconn/ingest_test/data/lenscorrection_igor/session01',
        'host': 'ibs-sharmi-ux1',
        'port': 9002,
        'workflow': 'at_2d_montage'
    }


def set_dict_values(metadata,list_key,list_val):
    for elements in range(0,len(list_key)) :
        key = list_key[elements]
        value = list_val[elements]
        metadata[key] = value
    return metadata

def get_img_and_metafiles(sessiondir, metadata):
    matchstr = ".*\.tif"
    imgfiles = []
    for chan in metadata:
        channame = chan['channel']
        d = os.path.join(sessiondir,channame)
        imgfiles.extend([os.path.join(d, f) for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)) and re.match(matchstr, f) ])

    metafiles = [ w.replace('.tif', '_metadata.txt') for w in imgfiles]
    imgfiles = [ w.replace(sessiondir+'/', '') for w in imgfiles]

    return imgfiles, metafiles

def get_session_number(sessiondir):
    tokens = sessiondir.split("session")
    return int(tokens[1])

def create_metafile(sessiondir):

    metadata = {}

    #acquisition_data - need to figure out how to populate the following:
    acq = {
        'microscope_type': 'Leica',
        'microscope': 'Igor',
        'camera': {
            'camera_id': '49600128',
            'model': 'Leica X'
        },
        'acquisition_time': '2018-03-08T03:07:19+00:00',
        'overlap': 0.12
    }

    with open(os.path.join(sessiondir,'session_metadata.txt')) as f:
        lines = f.readlines()
    acq = set_dict_values(acq,lines[0].split(), lines[1].split())
    assert  int(acq['#chan']) == len(lines)-5 # make sure that you have all the channels

    #channel information
    headings = ["channel","exposure_times","RLPosition"]
    d_channels = []
    for i in range(3, len(lines)-2):
        d = {}
        d = set_dict_values(d,headings,lines[i].split())
        d_channels.append(d)

    #data
    numtiles = int(acq['#chan']) * int(acq['MosaicX']) * int(acq['MosaicY'])
    tilefiles,metafiles = get_img_and_metafiles(sessiondir, d_channels)
    assert len(tilefiles) == numtiles & len(metafiles) == numtiles
    data = []
    for i in range (0, len(metafiles)):
        m = {}
        assert os.path.exists(metafiles[i])
        with open(metafiles[i]) as f:
            lines = f.readlines()

        m = set_dict_values(m,lines[0].split(), lines[1].split())
        m = set_dict_values(m,lines[2].split(), lines[3].split())
        m['img_path'] = tilefiles[i]
        data.append(m)

    #set metadata and output to file
    metadata['registration_series'] = get_session_number(sessiondir)
    metadata['acquisition_data'] = acq
    metadata['all_channels'] = d_channels
    metadata['data'] = data
    with open(os.path.join(sessiondir, "metadata.json"), 'w') as fp:
        json.dump(metadata, fp, indent=4)

class ATIngestTileSetModule(argschema.ArgSchemaParser):
    default_schema = ATIngestTileSetParams

    def ingest_message(self,host,port,workflow,message):
        url = 'http://%s:%s/workflow_engine/ingest/'%(host,port)
        r = requests.post(url=url+workflow, json=message)
        print(r.json())

    def run(self):

        #not decided if we want this here or in the monitor
        create_metafile(self.args['inputdir'])

        #read metafile - find json file in input directory
        matchstr = ".*\.json"
        inputdir = self.args['inputdir']
        metafile = [os.path.join(inputdir, f) for f in os.listdir(inputdir) if os.path.isfile(os.path.join(inputdir, f)) and re.match(matchstr, f) ][0]
        with open(metafile, 'r') as f:
            md = json.load(f)

        #todo: need to replace body with whatever is read from metadata file
        body = {}
        body['registration_series'] = md['registration_series']
        body['acquisition_data'] = md['acquisition_data']
        body['metafile'] = metafile
        body['reference_set_id'] = None

        self.ingest_message(self.args['host'], self.args['port'],self.args['workflow'],body)

        print ("hello at ingest")

if __name__ == "__main__":
    mod = ATIngestTileSetModule(input_data=example_input)
    mod.run()
