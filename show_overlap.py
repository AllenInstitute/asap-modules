import shapely
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt
import mpl_toolkits.mplot3d.art3d as art3d
import renderapi
from shapely.geometry import Polygon
from descartes.patch import PolygonPatch
import numpy as np

#specify the section
source_stack = 'RoughAlign_2266_3483'
z = 2316
intermediate_stack = 'intermediate_4tile'

#create a renderapi.connect.Render object
#start with the full stack
render_connect_params ={
    'host':'em-131fs',
    'port':8080,
    'owner':'danielk',
    'project':'EM_Phase1_Fine',
    'client_scripts':'\usr\local\render\render-ws-java-client\src\scripts',
    'memGB':'2G'
}
render = renderapi.connect(**render_connect_params)
source_bounds=renderapi.stack.get_stack_bounds(source_stack,render=render,owner='gayathri')
zmin = source_bounds['minZ']
zmax = source_bounds['maxZ']
rcs = []
#source_bounds=renderapi.stack.get_bounds_from_z(source_stack,z,render=render,owner='gayathri')
#inter_bounds=renderapi.stack.get_bounds_from_z(intermediate_stack,z,render=render)
zs = np.arange(zmin,zmax,50)
for iz in zs:
        rcs.append(renderapi.tilespec.get_tile_specs_from_z(source_stack,iz,render=render,owner='gayathri'))
        
#rcs = [rcsource_zmin,rcsource,rcsource_zmax,rcinter]
colors = ['b','b','b','g']
#zs = [zmin,z,zmax,z]
fig=plt.figure(1)
fig.clf()
ax = fig.add_subplot(111,projection='3d')
xmin = 1e9
xmax = -1e9
ymin = 1e9
ymax = -1e9

for i in np.arange(len(rcs)):
        rc = rcs[i]
        ntiles = len(rc)
        tileids = []
        polys = []
        patches = []
        for tile in rc:
        	tileids.append(tile.tileId)
        	pts = []
        	pts.append((tile.minX,tile.minY))
        	pts.append((tile.maxX,tile.minY))
        	pts.append((tile.maxX,tile.maxY))
        	pts.append((tile.minX,tile.maxY))
        	pts.append((tile.minX,tile.minY))
        	polys.append(Polygon(pts))
                xmin = tile.minX if tile.minX < xmin else xmin
                xmax = tile.maxX if tile.maxX > xmax else xmax
                ymin = tile.minY if tile.minY < ymin else ymin
                ymax = tile.maxY if tile.maxY > ymax else ymax
        
        for poly in polys:
        	patches.append(PolygonPatch(poly, facecolor='b', edgecolor='k', alpha=0.5, zorder=2))
        
        for patch in patches:
        	ax.add_patch(patch)
                art3d.pathpatch_2d_to_3d(patch, z=zs[i], zdir='z')
        #ax.set_xlim(source_bounds['minX']*0.9,source_bounds['maxX']*1.1)
        #ax.set_ylim(source_bounds['minY']*0.9,source_bounds['maxY']*1.1)
        
        #for i in np.arange(ntiles):
        	#tile = rcinter[i]
        	#ax.text(0.5*(tile.minX+tile.maxX),0.5*(tile.minY+tile.maxY),z,i+1)

ax.set_xlim(xmin*0.9,xmax*1.1)
ax.set_ylim(ymin*0.9,ymax*1.1)
ax.set_zlim(zmin*0.9,zmax*1.1)
ax.set_xlabel('x')
ax.set_ylabel('y')
ax.set_zlabel('z')
fig.show()
        
        
       
