import argschema
from argschema.fields import DateTime, Nested, InputDir, Str, Int, InputFile


class Camera(argschema.schemas.DefaultSchema):
    camera_id = Str(required=True)
    height = Int(required=False)
    width = Int(required=False)
    model = Str(required=False)


class AcquisitionData(argschema.schemas.DefaultSchema):
    camera = Nested(Camera, required=False)
    microscope = Str(required=False, description="")
    overlap = Int(required=False)
    acquisition_time = DateTime(required=True, format="iso")


class Section(argschema.schemas.DefaultSchema):
    z_index = Int(required=False, default=None, allow_none=True)
    # metadata = Nested(TAOid())
    specimen = Str(required=True, description="LIMS id of tissue block")
    # TODO specimen should be integer, but imaging metadata does not conform
    # specimen = Int(required=True, description="LIMS id of tissue block")
    sample_holder = Str(required=False)


class TileSetIngestSchema(argschema.ArgSchema):
    storage_directory = InputDir(
        required=True, description="")
    acquisition_data = Nested(AcquisitionData, required=False)


class EMMontageSetIngestSchema(TileSetIngestSchema):
    reference_set_id = Str(required=False, default=None, allow_none=True)
    section = Nested(Section, required=False,
                     description="")

class ReferenceSetIngestSchema(TileSetIngestSchema):
    manifest_path = InputFile(required=True)


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
