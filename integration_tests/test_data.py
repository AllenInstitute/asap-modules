import os
from jinja2 import Environment, FileSystemLoader
import json
import tempfile

render_host = os.environ.get(
    'RENDER_HOST', 'renderservice')
render_port = os.environ.get(
    'RENDER_PORT', 8080)
render_test_owner = os.environ.get(
    'RENDER_TEST_OWNER', 'test'
)
client_script_location = os.environ.get(
    'RENDER_CLIENT_SCRIPTS',
    ('/shared/render/render-ws-java-client/'
     'src/main/scripts/'))

render_params = {
    "host": render_host,
    "port": render_port,
    "owner": render_test_owner,
    "project": "test_project",
    "client_scripts": client_script_location
}

scratch_dir = os.environ.get(
    'SCRATCH_DIR', '/var/www/render/scratch/')
try:
    os.makedirs(scratch_dir)
except OSError as e:
    pass

log_dir = os.environ.get(
    'LOG_DIR', '/allen/aibs/pipeline/image_processing/volume_assembly/logs/')

try:
    os.makedirs(log_dir)
except OSError as e:
    pass

example_dir = os.path.join(os.path.dirname(__file__), 'test_files')
example_env = Environment(loader=FileSystemLoader(example_dir))

TEST_DATA_ROOT = os.environ.get(
    'RENDER_TEST_DATA_ROOT', '/allen/aibs/pipeline/image_processing/volume_assembly')

FIJI_PATH = os.environ.get(
    'FIJI_PATH', '/allen/aibs/pipeline/image_processing/volume_assembly/Fiji.app')


def render_json_template(env, template_file, **kwargs):
    template = env.get_template(template_file)
    d = json.loads(template.render(**kwargs))
    return d


# test data for dataimport testing
METADATA_FILE = os.path.join(example_dir, 'TEMCA_mdfile.json')

MIPMAP_TILESPECS_JSON = render_json_template(example_env, 'mipmap_tilespecs.json',
                                             test_data_root=TEST_DATA_ROOT)

cons_ex_tilespec_json = render_json_template(example_env, 'cycle1_step1_acquire_tiles.json',
                                             test_data_root=TEST_DATA_ROOT)

cons_ex_transform_json = render_json_template(example_env,  'cycle1_step1_acquire_transforms.json',
                                              test_data_root=TEST_DATA_ROOT)

multiplicative_correction_example_dir = os.path.join(
    TEST_DATA_ROOT, 'intensitycorrection_test_data')

MULTIPLICATIVE_INPUT_JSON = render_json_template(example_env, 'intensity_correction_template.json',
                                                 test_data_root=TEST_DATA_ROOT)
# lc_example_dir = os.environ.get('RENDER_MODULES_LC_TEST_DATA',
#     'allen/aibs/pipeline/image_processing/volume_assembly/lc_test_data/')


calc_lens_parameters = render_json_template(example_env, 'calc_lens_correction_parameters.json',
                                            test_data_root=TEST_DATA_ROOT,
                                            fiji_path=FIJI_PATH,
                                            test_output=tempfile.mkdtemp())

TILESPECS_NO_LC_JSON = render_json_template(example_env, 'test_noLC.json',
                                            test_data_root=TEST_DATA_ROOT)
TILESPECS_LC_JSON = render_json_template(example_env, 'test_LC.json',
                                         test_data_root=TEST_DATA_ROOT)

RAW_STACK_INPUT_JSON = render_json_template(example_env, 'raw_tile_specs_for_em_montage.json',
                                            test_data_root=TEST_DATA_ROOT)

MATLAB_SOLVER_PATH = os.environ.get('MATLAB_SOLVER_PATH',
    '/allen/aibs/pipeline/image_processing/volume_assembly/EMAligner/dev/allen_templates')
MONTAGE_SOLVER_BIN = os.path.join(MATLAB_SOLVER_PATH,'solve_montage_SL')

test_em_montage_parameters = render_json_template(example_env, 
    'run_montage_job_for_section_template.json',
    render_host=render_host,
    render_port=render_port,
    render_project="montage_test",
    render_owner = render_test_owner,
    render_client_scripts = client_script_location,
    em_solver_bin = MONTAGE_SOLVER_BIN,
    temp_dir= tempfile.mkdtemp(),
    scratch_dir = tempfile.mkdtemp())
