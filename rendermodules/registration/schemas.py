from argschema.fields import Str, Int, Boolean
from argschema.schemas import DefaultSchema
import marshmallow as mm 
from marshmallow import post_load
from ..module.render_module import RenderModule, RenderParameters


class RegisterSectionSchema(RenderParameters):
    reference_stack = Str(
        required=True,
        descritption="Reference stack to which section needs to be registered to")
    moving_stack = Str(
        required=True,
        description="Moving stack with section that needs to be registered to ref stack")
    output_stack = Str(
        required=True,
        description="Output stack with moving section registered to ref section")
    match_collection = Str(
        required=True,
        description="Match collection storing the pt matches between the ref and moving section tiles")
    match_owner = Str(
        required=False,
        default=None,
        missing=None,
        description="Match collection owner")
    registration_model = Str(
        required=False,
        default="Affine",
        missing="Affine",
        validate=mm.validate.OneOf(["Affine", "Rigid", "Similarity"]),
        description="Registration transformation model (Affine or Rigid) Default - Affine")
    reference_z = Int(
        required=True,
        description="Z index of the section in reference stack")
    moving_z = Int(
        required=True,
        description="Z index of the moving section")
    overwrite_output = Boolean(
        required=False,
        default=True,
        missing=True,
        description="Do you want to overwrite output stack if section already exists in it (Default - True)")
    consolidate_transforms = Boolean(
        required=False,
        default=True,
        missing=True,
        description="Consolidate transforms in tilespecs if set to True (Default=True)")

    @post_load
    def validate_data(self, data):
        if data['match_owner'] is None:
            data['match_owner'] = data['render']['owner']
    
class RegisterSectionOutputSchema(DefaultSchema):
    out_stack = Str(
        required=True,
        description="output stack to which the registered section is written to")
    registered_z = Int(
        required=True,
        description="Z index of the registered section in output stack")