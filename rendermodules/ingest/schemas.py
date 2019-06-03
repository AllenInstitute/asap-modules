import logging

import argschema
from argschema.fields import DateTime, Nested, InputDir, Str, Int
import marshmallow
import pathlib2 as pathlib

import rendermodules.utilities.schema_utils


class Camera(argschema.schemas.DefaultSchema):
    camera_id = Str(required=True)
    height = Int(required=False)
    width = Int(required=False)
    model = Str(required=False)


class AcquisitionData(argschema.schemas.DefaultSchema):
    camera = Nested(Camera, required=False)
    microscope = Str(required=False, description="")
    overlap = Int(required=False)
    acquisition_time = DateTime(required=True)


class Section(argschema.schemas.DefaultSchema):
    z_index = Int(required=False, default=True)
    # metadata = Nested(TAOid())
    specimen = Int(required=True, description="LIMS id of tissue block")
    sample_holder = Str(required=False)


class TileSetIngestSchema(argschema.ArgSchema):
    storage_directory = InputDir(
        required=False, description=(
            "Directory which stores acquisition data. "
            "Non-file uris must use storage_prefix"))
    storage_prefix = Str(required=True, description=(
        "uri prefix for acquisition data."))
    section = Nested(Section, required=False,
                     description="")
    acquisition_data = Nested(AcquisitionData, required=False)

    # TODO test this
    @marshmallow.pre_load
    def directory_to_storage_prefix(self, data):
        rendermodules.utilities.schema_utils.posix_to_uri(
            data, "storage_directory", "storage_prefix")


class EMMontageSetIngestSchema(TileSetIngestSchema):
    reference_set_id = Str(required=False, default=None)


class ReferenceSetIngestSchema(TileSetIngestSchema):
    pass


example = {
    "reference_set_id": "DEADBEEF",
    "acquisition_data": {
        "microscope": "temca2",
        "camera": {
            "camera_id": "4450428",
            "height": 3840,
            "width": 3840,
            "model": "Ximea CB200MG"
        },
        "overlap": 0.07,
        "acquisition_time": "2017-08-29T13:01:46"
    },
    "section": {
        "z_index": 1050,
        "specimen": 594089217,
        "sample_holder": "reel0"
    },
    "storage_directory": "/allen/programs/celltypes/workgroups/em-connectomics/data/workflow_test_sqmm/001050/0/"
}

if __name__ == "__main__":
    p = argschema.ArgSchemaParser(
        input_data=example, schema_type=EMMontageSetIngestSchema)
