import os
from jinja2 import Environment, FileSystemLoader
import os
import json

render_host = os.environ.get(
    'RENDER_HOST', 'renderservice')
render_port = os.environ.get(
    'RENDER_PORT', 8080)
client_script_location = os.environ.get(
    'RENDER_CLIENT_SCRIPTS',
    ('/var/www/render/render-ws-java-client/'
     'src/main/scripts/'))

scratch_dir = os.environ.get(
    'SCRATCH_DIR', '/var/www/render/scratch/')
try:
    os.makedirs(scratch_dir)
except OSError as e:
    pass

example_dir = os.path.join(os.path.dirname(__file__), 'test_files')
env = Environment(loader=FileSystemLoader(example_dir))

TEST_DATA_ROOT = os.environ.get(
    'RENDER_TEST_DATA_ROOT', '/allen/aibs/pipeline/image_processing/volume_assembly')

FIJI_PATH = os.environ.get(
    'FIJI_PATH', '/allen/aibs/pipeline/image_processing/volume_assembly/Fiji.App')

def render_json_template(env,template_file,**kwargs):
    template = env.get_template(template_file)
    d = json.loads(template.render(**kwargs))
    return d

calc_lens_parameters = render_json_template(env,'calc_lens_correction_parameters.json',
    test_data_root=TEST_DATA_ROOT, fiji_path=FIJI_PATH)

# test data for dataimport testing
METADATA_FILE = os.path.join(example_dir, 'TEMCA_mdfile.json')

MIPMAP_TILESPECS_JSON = render_json_template(env, 'mipmap_tilespecs.json',
    test_data_root=TEST_DATA_ROOT)

cons_ex_tilespec_json = render_json_template(env, 'cycle1_step1_acquire_tiles.json',
    test_data_root=TEST_DATA_ROOT)

cons_ex_transform_json = render_json_template(env,  'cycle1_step1_acquire_transforms.json',
    test_data_root=TEST_DATA_ROOT)

multiplicative_correction_example_dir=os.path.join(TEST_DATA_ROOT,'intensitycorrection_test_data')

MULTIPLICATIVE_INPUT_JSON = render_json_template(env,  'DAPI_1_rib0000sess0001sect0000.json',
    test_data_root=TEST_DATA_ROOT)
