import os

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

# test data for dataimport testing
METADATA_FILE = os.path.join(example_dir, 'TEMCA_mdfile.json')
MIPMAP_TILESPECS_JSON = os.path.join(example_dir, 'mipmap_tilespecs.json')

example_dir_env = os.environ.get(
     'RENDER_EXAMPLE_DATA', '/var/www/render/examples/')

tilespec_file = os.path.join(
     example_dir_env, 'example_1', 'cycle1_step1_acquire_tiles.json')
tform_file = os.path.join(
     example_dir_env, 'example_1', 'cycle1_step1_acquire_transforms.json')

multiplicative_correction_example_dir = os.environ.get('RENDER_MODULES_MC_TEST_DATA',
    '/allen/aibs/pipeline/image_processing/volume_assembly/intensitycorrection_test_data/')

MULTIPLICATIVE_INPUT_JSON = os.path.join(multiplicative_correction_example_dir,'DAPI_1_rib0000sess0001sect0000.json')

# lc_example_dir = os.environ.get('RENDER_MODULES_LC_TEST_DATA',
#     'allen/aibs/pipeline/image_processing/volume_assembly/lc_test_data/')

lc_example_dir = '/allen/aibs/pipeline/image_processing/volume_assembly/lc_test_data/'

TILESPECS_NO_LC_JSON = os.path.join(lc_example_dir, 'test_noLC.json')
TILESPECS_LC_JSON = os.path.join(lc_example_dir, 'test_LC.json')