import os

render_host = os.environ.get('RENDER_HOST','renderservice')
render_port = os.environ.get('RENDER_PORT',8080)
client_script_location = os.environ.get('RENDER_CLIENT_SCRIPTS',
                          ('/var/www/render/render-ws-java-client/'
                          'src/main/scripts/'))
example_dir = os.environ.get('RENDER_EXAMPLE_DATA','/var/www/render/examples/')
tilespec_file = os.path.join(example_dir,'example_1','cycle1_step1_acquire_tiles.json')
tform_file = os.path.join(example_dir,'example_1','cycle1_step1_acquire_transforms.json')
