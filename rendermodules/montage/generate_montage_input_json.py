import json
import os
import subprocess
from argschema.fields import Bool, Float, Int, Nested, Str, InputDir
from argschema.schemas import DefaultSchema
import marshmallow as mm
import renderapi
from ..module.render_module import RenderModule, RenderParameters

"""
This script generates a json file to feed into the matlab solver
It takes in a series of options for the solver and validates the input
"""

if __name__ == "__main__" and __package__ is None:
    __package__ = "rendermodules.montage.generate_montage_input_json"


example = {
    "render": {
        "host": "http://em-131fs",
        "port": 8998,
        "owner": "gayathri",
        "project": "MM2",
        "client_scripts": "/allen/programs/celltypes/workgroups/em-connectomics/gayathrim/nc-em2/Janelia_Pipeline/render_20170613/render-ws-java-client/src/main/scripts"
    },
    
}
