import marshmallow as mm
from ..module.render_module import RenderParameters
from argschema.fields import Bool, Float, Int, Str, InputDir


class DetectMontageDefectsParameters(RenderParameters):
    prestitched_stack = Str(
        required=True,
        description='Pre stitched stack (raw stack)')
    poststitched_stack = Str(
        required=True,
        description='Stitched montage stack')
    zstart = Int(
        required=True,
        description='start z index of section')
    zend = Int(
        required=True,
        description='end z index of section')
    plot_sections = Bool(
        required=False,
        default=False,
        missing=False,
        description="Do you want to plot the sections with defects?. Will plot Bokeh plots in a html file")
    out_html = InputDir(
        required=False,
        default=None,
        missing=None,
        description="Folder to save the Bokeh plot defaults to /tmp directory")
    pool_size = Int(
        required=False,
        default=10,
        missing=10,
        description='Number of cores for parallel processing')
