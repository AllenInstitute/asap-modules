import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection,LineCollection
from matplotlib.patches import Polygon
from scipy.spatial import Voronoi
import mpl_scatter_density
import numpy as np

def make_plots(meshobj):
    fig1 = plt.figure(1)
    fig1.clf()
    ax1=fig1.add_subplot(231,projection='scatter_density')
    ax2=fig1.add_subplot(232,projection='scatter_density')
    ax4=fig1.add_subplot(234,projection='scatter_density')
    ax5=fig1.add_subplot(235,projection='scatter_density')
    plot_residuals(meshobj,fig1,ax1,ax4,ax2,ax5)
    ax3=fig1.add_subplot(233)
    ax6=fig1.add_subplot(236)
    plot_solution(meshobj,fig1,ax3,ax6)

def plot_mesh_and_points(meshobj,ax):
    pc=[]
    for tri in meshobj.mesh.simplices:
       pc.append(Polygon(meshobj.mesh.points[tri]))
    pcoll = PatchCollection(pc,edgecolors=[0.,0.,0.,1.],facecolors=[0,1.,1.,0.3],linewidth=0.1)
    ax.scatter(meshobj.coords[:,0],meshobj.coords[:,1],marker='.',c='r',s=0.8)
    ax.add_collection(pcoll)
    ax.set_aspect('equal')
    plt.title('point matches and mesh')

def max_res(dx,dy):
    r = np.sqrt(np.power(dx,2.0),np.power(dy,2.0)) 
    return r.max()

def make_quiver(xp,yp,dx,dy,ax,scale=1.0):
    lmesh = ax.quiver(xp,yp,dx,dy,units='x',color='b',scale_units='x',scale=scale)
    buff=600
    ax.set_xlim((xp+dx).min()-buff,(xp+dx).max()+buff)
    ax.set_ylim((yp+dy).min()-buff,(yp+dy).max()+buff)
    ax.set_aspect('equal')
    ax.patch.set_color([0.8,0.8,0.8])
    ax.invert_yaxis()

def dr_hist(dx,dy,ax):
    ax.hist(np.sqrt(dx**2+dy**2))
    ax.set_xlabel("correction size [pixels]")
    ax.set_ylabel("count")

def plot_estimate(meshobj,fig,ndim=5):
    [[xp,yp],[dxp,dyp],[pxp,pyp]] = meshobj.estimate_polynomial(nx=30,ny=30,ndim=ndim)
    xp = xp.flatten()
    yp = yp.flatten()
    dxp = dxp.flatten()
    dyp = dyp.flatten()
    pxp = pxp.flatten()
    pyp = pyp.flatten()
    xlim = (xp.min()-200,xp.max()+200)
    ylim = (yp.min()-200,yp.max()+200)

    fig.clf()

    scale=0.1
    dx = xp-pxp
    dy = yp-pyp
    rmax = max_res(dx,dy)
    ax1=fig.add_subplot(231)
    make_quiver(xp,yp,dx,dy,ax1,scale=scale)
    ax1.set_title('fit poly distortion\nmaximum = %0.1f pixels'%(rmax))
    ax1.legend(['arrow scale %0.1fx'%(1.0/scale)],loc=3,fontsize=8)
    dr_hist(dx,dy,fig.add_subplot(234))

    dx = xp-dxp
    dy = yp-dyp
    rmax = max_res(dx,dy)
    ax2=fig.add_subplot(232)
    make_quiver(xp,yp,dx,dy,ax2,scale=scale)
    title=meshobj.tilespecs[0].layout.scopeId+'\nfirst tid: '+meshobj.tilespecs[0].tileId
    title+='\nfit mesh distortion\nmaximum = %0.1f pixels'%(rmax)
    ax2.set_title(title)
    ax2.legend(['arrow scale %0.1fx'%(1.0/scale)],loc=3,fontsize=8)
    dr_hist(dx,dy,fig.add_subplot(235))

    scale=0.02
    dx=pxp-dxp
    dy=pyp-dyp
    rmax = max_res(dx,dy)
    ax3=fig.add_subplot(233)
    make_quiver(xp,yp,dx,dy,ax3,scale=scale)
    ax3.set_title('difference plot \nmaximum = %0.1f pixels'%(rmax))
    ax3.legend(['arrow scale %0.1fx'%(1.0/scale)],loc=3,fontsize=8)
    dr_hist(dx,dy,fig.add_subplot(236))


def plot_vector(meshobj,fig,nx=100,ny=100,exfactor=1):
    [xp,yp,idx,idy] = meshobj.interpolate(nx=nx,ny=ny,flatten=True)
    idr = np.sqrt(np.power(idx,2.0)+np.power(idy,2.0))
    lines=[]
    for i in range(xp.size):
        line =[(xp[i]-exfactor*idx[i]/2.,yp[i]-exfactor*idy[i]/2.)]
        line+=[(xp[i]+exfactor*idx[i]/2.,yp[i]+exfactor*idy[i]/2.)]
        lines.append(line)
    LC = LineCollection(lines,color='b')

    ax=fig.add_subplot(221)
    ax.add_collection(LC)
    ax.set_xlim(xp.min()-100,xp.max()+100)
    ax.set_ylim(yp.min()-100,yp.max()+100)
    ax.set_aspect('equal')
    ax.patch.set_color([0.9,0.9,0.9])
    ax.invert_yaxis()

    ax2=fig.add_subplot(222)
    ct=[]
    rl=[]
    rl.append('residual max [pixels]')
    ct.append(('%0.2f'%idr.max(),))
    rl.append('dx [min,max]')
    ct.append(('[%0.2f,%0.2f]'%(idx.min(),idx.max()),))
    rl.append('dy [min,max]')
    ct.append(('[%0.2f,%0.2f]'%(idy.min(),idy.max()),))

    clust_data = np.random.random((10,3))
    collabel=("","")
    t=ax2.table(cellText=ct,colLabels=collabel,rowLabels=rl,loc='center',colWidths=[0.5])
    t.auto_set_column_width([-1,0])
    t.set_fontsize(20)
    t.scale(1, 4)
    ax2.set_title(meshobj.tilespecs[0].layout.scopeId+'\nfirst tid: '+meshobj.tilespecs[0].tileId,horizontalalignment='right')
    ax2.axis('off')

def plot_solution(meshobj,fig,ax1,ax2):
    cmap = plt.cm.plasma_r
    [xp,yp,idx,idy] = meshobj.interpolate()

    imx=ax1.imshow(idx,interpolation='nearest',extent=[xp.min(),xp.max(),yp.max(),yp.min()],cmap=cmap,vmin=-3,vmax=3)
    ax1.invert_yaxis()
    ax1.set_aspect('equal')
    fig.colorbar(imx,ax=ax1)

    imy=ax2.imshow(idy,interpolation='nearest',extent=[xp.min(),xp.max(),yp.max(),yp.min()],cmap=cmap,vmin=-3,vmax=3)
    ax2.invert_yaxis()
    ax2.set_aspect('equal')
    fig.colorbar(imy,ax=ax2)

    #v=Voronoi(meshobj.mesh.points)
    #pc = []
    #for i in range(meshobj.mesh.npoints):
    #    region = v.regions[v.point_region[i]]
    #    if -1 in region:
    #        region.remove(-1)
    #    pc.append(Polygon(v.vertices[region]))

    #xpcoll = PatchCollection(pc,edgecolors=[0.,0.,0.,1.],facecolors=[0,1.,1.,0.3],linewidth=0.1,cmap=cmap)
    #xpcoll.set_array(meshobj.solution[0][meshobj.lens_dof_start:])
    #ax1.scatter(meshobj.mesh.points[:,0],meshobj.mesh.points[:,1],marker='.',c='r',s=1.8)
    #ax1.add_collection(xpcoll)
    #ax1.set_aspect('equal')
    #ax1.set_title('dx lens correction solution')
    #xpcoll.set_clim(-3,3)
    #fig.colorbar(xpcoll,ax=ax1)

    #ypcoll = PatchCollection(pc,edgecolors=[0.,0.,0.,1.],facecolors=[0,1.,1.,0.3],linewidth=0.1,cmap=cmap)
    #ypcoll.set_array(meshobj.solution[1][meshobj.lens_dof_start:])
    #ax2.scatter(meshobj.mesh.points[:,0],meshobj.mesh.points[:,1],marker='.',c='r',s=1.8)
    #ax2.add_collection(ypcoll)
    #ax2.set_aspect('equal')
    #ax2.set_title('dy lens correction solution')
    #ypcoll.set_clim(-3,3)
    #fig.colorbar(ypcoll,ax=ax2)

def plot_transforms(meshobj,fig):
    fig.clf()
    scale=np.zeros((len(meshobj.tilespecs),2))
    translation=np.zeros((len(meshobj.tilespecs),2))
    shear=np.zeros(len(meshobj.tilespecs))
    rotation=np.zeros(len(meshobj.tilespecs))
    polys=[]

    for i in range(len(meshobj.tilespecs)):
        ts=meshobj.tilespecs[i]
        tf=meshobj.transforms[i]
        polys.append(Polygon(tf.tform(ts.bbox_transformed(ndiv_inner=0,tf_limit=0))))
        scale[i]=tf.scale
        shear[i]=tf.shear
        rotation[i]=tf.rotation
        translation[i]=tf.translation

def plot_residuals(meshobj,fig,ax1,ax2,ax3,ax4):
    cmap = plt.cm.plasma_r
    [p,q,pt,qt]=meshobj.transform_pq()
    p=np.concatenate(p)
    q=np.concatenate(q)
    pt=np.concatenate(pt)
    qt=np.concatenate(qt)
    xya = 0.5*(pt+qt)
    
    d1 = ax1.scatter_density(xya[:,0],xya[:,1],c=meshobj.errx,cmap=cmap)
    fig.colorbar(d1,ax=ax1)
    d2 = ax2.scatter_density(xya[:,0],xya[:,1],c=meshobj.erry,cmap=cmap)
    fig.colorbar(d2,ax=ax2)
    d1.set_clim(-3,3)
    d2.set_clim(-3,3)
    ax1.set_title('montage residuals')

    xyt = np.vstack((p,q))
    dx = np.concatenate([meshobj.errx,-meshobj.errx])
    dy = np.concatenate([meshobj.erry,-meshobj.erry])
    
    d3 = ax3.scatter_density(xyt[:,0],xyt[:,1],c=dx,cmap=cmap)
    fig.colorbar(d3,ax=ax3)
    d4 = ax4.scatter_density(xyt[:,0],xyt[:,1],c=dy,cmap=cmap)
    fig.colorbar(d4,ax=ax4)
    d3.set_clim(-3,3)
    d4.set_clim(-3,3)
    ax3.set_title('montage residuals in tilecoords')

