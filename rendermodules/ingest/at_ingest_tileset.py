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
from at_utils import *

example_input= {
        'inputdir': '/allen/programs/celltypes/production/incoming/shotconn/ingest_test/data/lenscorrection_igor/session01',
        'host': 'ibs-sharmi-ux1',
        'port': 9002,
        'workflow': 'at_2d_montage'

    }




class ATIngestTileSetModule(argschema.ArgSchemaParser):
    default_schema = ATIngestTileSetParams

    def ingest_message(self,host,port,workflow,message):
        url = 'http://%s:%s/workflow_engine/ingest/'%(host,port)
        r = requests.post(url=url+workflow, json=message)
        print(r.json())

    def run(self):

        #not decided if we want this here or in the monitor
        #create_metafile(self.args['inputdir'])

        #read metafile - find json file in input directory
        matchstr = ".*\.json"
        inputdir = self.args['inputdir']
        print("This is inputdir")
        print(inputdir)
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
