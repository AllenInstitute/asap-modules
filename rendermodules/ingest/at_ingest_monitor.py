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

class IngestMonitorException(Exception):
    pass


class SendAcquisitionModule(at_ingest_tileset.ATIngestTileSetModule):
    default_schema = SendAcquisitionParameters
    copy_cmd = ['gsutil', '-m', 'cp', '-rn']
    inactive_sleep_seconds = 300
    inactive_timer = datetime.timedelta(hours=1)

    def transfer_directory(self,inputdirs,outputdir):
        #copy storage_directory
        print (inputdirs)
        run_copy_command(self,inputdirs[0], outputdir)

        #create json - not decided if it should be here or in the ingest ingest_client- probably here
        #create_metafile(self.args['ingest_client']['inputdir'])

        #run ingest ingest_client
        #_ = at_ingest_tileset.ATIngestTileSetModule(input_data=ingestinput).run()
        return datetime.datetime.now()

    def startmonitor(self, inputdirs, outputdir, fillpercentage, mondirs=None):

        last_transfer = datetime.datetime.now()
        print (last_transfer)
        is_active = True
        while True:
            if not is_active:
                self.logger.debug(
                    "monitor is inactive -- last transfer at {}. "
                    "Sleeping for {}s".format(last_transfer, self.inactive_sleep_seconds))
                time.sleep(self.inactive_sleep_seconds)
            if get_used_space_percentage(outputdir) < fillpercentage:
                print("percentage")
                print (get_used_space_percentage(outputdir))
                try:
                    last_transfer = self.transfer_directory(inputdirs, outputdir)
                except IngestMonitorException:
                    self.logger.debug("Nothing to transfer.")
                    time.sleep(self.noCandidate_sleep_seconds)
            else:
                self.logger.warning(
                    'cannot transfer due to space limitations: {} '
                    'occupied with threshold {}.'.format(
                        get_used_space_percentage(outputdir), fillpercentage))
                time.sleep(self.insufficient_space_sleep_seconds)

            is_active = ((datetime.datetime.now() - last_transfer) <self.inactive_timer)

    def run(self):
        self.startmonitor(self.args['indirs'], self.args['outdir'],self.args['fillpercentage'])


if __name__ == "__main__":
    sendrunner = SendAcquisitionModule(input_data=example_input)
    sendrunner.run()
