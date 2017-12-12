#!/usr/bin/env python
'''
Ingest EM tile directory

Send EM tileset data using blue sky's celery ingest call
'''
import os
import re
import json
import datetime
import pytz

import argschema
from marshmallow import ValidationError

from rendermodules.ingest.schemas import (
    EMMontageSetIngestSchema, ReferenceSetIngestSchema,
    IngestParams, IngestTileSetParams)
from rendermodules.module.render_module import RenderModuleException

from workflow_client import celery_ingest

example_input = {
    "tile_dir": "/allen/aibs/pipeline/image_processing/volume_assembly/dataimport_test_data/",
    "metafile": None,
    "ingest_params": {
        "app_key": "at_em_imaging_workflow",
        "workflow_name": "em_2d_montage"
    }
}


class IngestTileSetModule(argschema.ArgSchemaParser):
    default_schema = IngestTileSetParams
    app_key = "at_em_imaging_workflow"
    workflow_name = "em_2d_montage"

    microscope_type = "TEMCA"
    timezone = 'America/Los_Angeles'

    # regular expression used to find metadata files
    meta_re = '_metadata_.*.json'

    # regex to determine if basename is lens correction
    lc_re = '_metadata_.*reference.*.json'

    # regex to find manifest file
    manifest_re = '_trackem_.*.txt'

    @staticmethod
    def _find_file_matching_re_in_dir(d, match_re):
        return [os.path.join(d, f) for f in os.listdir(d)
                if os.path.isfile(os.path.join(d, f)) and
                re.match(match_re, f)][0]

    @classmethod
    def find_metafile_in_dir(cls, d):
        return cls._find_file_matching_re_in_dir(d, cls.meta_re)

    @classmethod
    def find_manifest_in_dir(cls, d):
        return cls._find_file_matching_re_in_dir(d, cls.manifest_re)

    @classmethod
    def is_lcmetafile(cls, fn):
        return bool(re.match(cls.lc_re, os.path.basename(fn)))

    @staticmethod
    def validate_body(body, schema):
        v = schema().validate(body)
        if v:
            raise RenderModuleException(
                "Invalid schema for {} -- errors: {}".format(schema, v))
        return True

    @staticmethod
    def dump_body(body, schema):
        output_json, errors = schema().dump(body)
        if errors:
            raise ValidationError("{}".format(errors))
        else:
            return output_json

    @classmethod
    def send(cls, body_data, app_key=None, workflow_name=None, fix_option=[]):
        app_key = (cls.app_key if app_key is None else app_key)
        workflow_name = (cls.workflow_name if workflow_name
                         is None else workflow_name)

        return celery_ingest.ingest(
            app_key, workflow_name, body_data, fix_option)

    @classmethod
    def lcsend(cls, body_data, **kwargs):
        d = cls.dump_body(body_data, ReferenceSetIngestSchema)
        # cls.validate_body(body_data, ReferenceSetIngestSchema)
        return cls.send(d, fix_option=["ReferenceSet"], **kwargs)

    @classmethod
    def montagesend(cls, body_data, **kwargs):
        d = cls.dump_body(body_data, EMMontageSetIngestSchema)
        # cls.validate_body(body_data, EMMontageSetIngestSchema)
        return cls.send(d, fix_option=["EMMontageSet"], **kwargs)

    @classmethod
    def gen_datetime(cls, timestr, tz=None):
        tz = (tz if tz else cls.timezone)
        return pytz.timezone(tz).localize(
            datetime.datetime.strptime(timestr, '%Y%m%d%H%M%S'))

    @classmethod
    def gen_timestring(cls, timestr, **kwargs):
        return cls.gen_datetime(timestr, **kwargs).isoformat()

    def run(self):
        self.app_key = self.args['ingest_params']['app_key']
        self.workflow_name = self.args['ingest_params']['workflow_name']

        mdfile = (self.find_metafile_in_dir(self.args['tile_dir'])
                  if self.args.get(
                       'metafile') is None else self.args['metafile'])
        is_lc = self.is_lcmetafile(mdfile)

        with open(mdfile, 'r') as f:
            md = json.load(f)

        # TODO make work with reference set id
        body = {
            "acquisition_data": {
                "microscope": md[0]['metadata']['temca_id'],
                "microscope_type": self.microscope_type,
                "camera": {
                    "camera_id": md[0]['metadata']['camera_info']['camera_id'],
                    "height": md[0]['metadata']['camera_info']['height'],
                    "width": md[0]['metadata']['camera_info']['width'],
                    "model": md[0]['metadata']['camera_info']['camera_model']
                },
                "overlap": md[0]['metadata']['overlap'],
                "acquisition_time": self.gen_datetime(
                    md[0]['metadata']['roi_creation_time']),
            },
            "storage_directory": self.args['tile_dir'],
            "metafile": mdfile
        }

        if is_lc:
            body['manifest_path'] = (
                self.find_manifest_in_dir(self.args['tile_dir'])
                if self.args.get('manifest_path') is None
                else self.args['manifest_path'])
            response = self.lcsend(body)
        else:
            body['section'] = {
                "z_index": md[0]['metadata']['grid'],  # FIXME based on autoz
                "specimen": md[0]['metadata']['specimen_id'],  # FIXME not LIMS
                "sample_holder": md[0]['metadata']['grid']
            }
            response = self.montagesend(body)

        self.logger.info("celery ingest returned {}".format(response))
        self.logger.info("enqueued object: ".format(
            response['enqueued_object_uid']))

        return response


if __name__ == "__main__":
    mod = IngestTileSetModule(input_data=example_input)
    mod.run()
