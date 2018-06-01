import os
import subprocess
import datetime
import time
import imghdr
import json
import re
import errno
import pytz
import dateutil.parser
import marshmallow
import argschema
from argschema.fields import List, InputDir, OutputDir, Float, Str, Nested
from at_utils import *
from rendermodules.ingest import at_ingest_tileset
from schemas import ATIngestTileSetParams,SendAcquisitionParameters


#from rendermodules.ingest.schemas import IngestParams
#from rendermodules.ingest import ingest_tileset

example_input = {
    "project": "sharmitest",
    "indirs": ["/nas5/data/lens_corr_igor/raw/data/Ribbon0001/session01/"],
    "outdir": "/allen/programs/celltypes/production/incoming/shotconn/ingest_test/data/",
    "fillpercentage": 0.7,
    "copy_method": "gsutil",
    "ingest_client": {
            'inputdir': '/allen/programs/celltypes/production/incoming/shotconn/ingest_test/data/lenscorrection_igor/session01',
            'host': 'ibs-sharmi-ux1',
            'port': 9002,
            'workflow': 'at_2d_montage'
    }
}

class IngestTriggerException(Exception):
    pass


class SendAcquisitionModule(at_ingest_tileset.ATIngestTileSetModule):
    default_schema = SendAcquisitionParameters
    copy_cmd = ['rsync','-rltzuv']
    #copy_cmd = ['cp','-rn']
    def transfer_directory(self,inputdirs,outputdirs, project,ingestinput):

        assert len(inputdirs) == len(outputdirs)

        for i in range(0,len(inputdirs)):
            #copy storage_directory
            if not os.path.exists(outputdirs[i]):
                os.makedirs(outputdirs[i])
            run_copy_command(self,inputdirs[i], outputdirs[i])

            #create json - not decided if it should be here or in the ingest ingest_client- probably here
            create_metafile(outputdirs[i],project)

            #run ingest ingest_client
            ingestinput['inputdir'] = outputdirs[i]
            _ = at_ingest_tileset.ATIngestTileSetModule(input_data=ingestinput).run()

        return datetime.datetime.now()

    def trigger(self, inputdirs, outputdir, fillpercentage):

        #create outputdirs
        outputdirs = []
        for inputdir in inputdirs:
            ribbonandsession = parse_inputdir(inputdir)
            outputdirs.append(os.path.join(outputdir, self.args['project'], ribbonandsession))

        if get_used_space_percentage(outputdir) < fillpercentage:
            try:
                last_transfer = self.transfer_directory(inputdirs, outputdirs, self.args['project'],self.args['ingest_client'])
            except IngestTriggerException:
                self.logger.debug("Nothing to transfer.")
        else:
            self.logger.warning(
                'cannot transfer due to space limitations: {} '
                'occupied with threshold {}.'.format(
                    get_used_space_percentage(outputdir), fillpercentage))

    def run(self):
        self.trigger(self.args['indirs'], self.args['outdir'],self.args['fillpercentage'])


if __name__ == "__main__":
    sendrunner = SendAcquisitionModule(input_data=example_input)
    sendrunner.run()
