# This is a wrapper to run galfit from python
import numpy as np
from subprocess import Popen, PIPE
import pyfits


def CreateFile(Iimg, region, models, sky='Default', fout=None, **kwargs):
    '''
        Creates a file to be run with galfit
        options can be given through kwargs
        models is a list of dicts where the keys are the model parameters.
        Note that region includes the initial pixel, ie, a box from 200 to 300 will have 101 pixels, in python this will be a[199:300]
        Example sersic model:
        {
         0  : 'sersic',      #  object type
         1  : '250 490 1 1', #  position x, y
         3  : '12. 1',       #  Integrated magnitude
         4  : '9 1',         #  R_e (half-light radius)   [pix]
         5  : '1.5 1',       #  Sersic index n (de Vaucouleurs n=4)
        'c0': '0 1',         #  Boxyness
         9  : '1 1',         #  axis ratio (b/a)
        10  : '0 1',         #  position angle (PA) [deg: Up=0, Left=90]
        'Z' :  0}            #  output option (0 = resid., 1 = Don't subtract)
    '''
    if len(models) == 0:
        print 'Need at least one model!'
        return 1
    defdict = {
        'Iimg': Iimg,  # Input data image (FITS file)
        'Oimg': 'out.fits',  # Output data image block
        'Simg': '',  # Sigma Image
        'Pimg': 'none',  # PSF Image
        'PSFf': '1',  # PSF fine sampling factor
        'badmask': 'none',  # Bad pixel mask (FITS image or ASCII coord list)'
        'constr': 'none',  # File with parameter constraints (ASCII file) '
        'region': '{0} {1} {2} {3}'.format(region[0], region[1], region[2], region[3]), # Image region to fit (xmin xmax ymin ymax)'
        'convbox': '100 100',  # Size of the convolution box (x y)'
        'ZP': '0',  # Magnitude photometric zeropoint '
        'scale': '0.03 0.03',  # Plate scale (dx dy)    [arcsec per pixel]'
        'dispt': 'regular',  # Display type (regular, curses, both)'
        'opt': '0',  # Choose: 0=optimize, 1=model, 2=imgblock, 3=subcomps'
    }
    defdict.update(kwargs)

    fout = open(fout, 'w')
    fout.write('A) {0} \n'.format(defdict['Iimg']))
    fout.write('B) {0} \n'.format(defdict['Oimg']))
    fout.write('C) {0} \n'.format(defdict['Simg']))
    fout.write('D) {0} \n'.format(defdict['Pimg']))
    fout.write('E) {0} \n'.format(defdict['PSFf']))
    fout.write('F) {0} \n'.format(defdict['badmask']))
    fout.write('G) {0} \n'.format(defdict['constr']))
    fout.write('H) {0} \n'.format(defdict['region']))
    fout.write('I) {0} \n'.format(defdict['convbox']))
    fout.write('J) {0} \n'.format(defdict['ZP']))
    fout.write('K) {0} \n'.format(defdict['scale']))
    fout.write('O) {0} \n'.format(defdict['dispt']))
    fout.write('P) {0} \n'.format(defdict['opt']))

    emodels = list(models)
    if sky == 'Default':
        sky = {'0': 'sky', '1': '1 1', '2': '0 0',
               '3': '0 0', 'Z': 0, 'Comment': 'StandardSky'}
    if sky != 'None':
        emodels.append(sky)
    for model in emodels:
        if 'Comment' in model:
            fout.write('#{0} \n'.format(model['Comment']))
        for i in np.argsort(model.keys()):
            key = model.keys()[i]
            if key == 'Comment':
                continue
            fout.write('{0}) {1} \n'.format(key, model[key]))
    fout.close()
    return 0


def rungalfit(infile, outfile='out.fits', timeout=300, verb=True):
    # galfit needs to be in the path
    # will run here, so file either needs to be complete path, or here...
    Popen(["rm", outfile], stderr=PIPE)
    p = Popen(["timeout", str(timeout), "galfit", infile], stdout=PIPE)
    ES = p.wait()
    pout = p.stdout.readlines()
    if ES == 124:
        if verb:
            for l in pout:
                print l[:-1]
        if verb:
            print 'Process timeout...'
        return pout, [-1, -1, -1, -1], [], 124
    try:
        outfit = pyfits.open(outfile)
        models = []
        for mod in [x for x in outfit[2].header if 'COMP' in x]:
            models.append({mod: outfit[2].header[mod]})
            for key in [x for x in outfit[2].header if mod[5:]+'_' in x]:
                if verb:
                    print key, outfit[2].header[key]
                models[-1][key] = outfit[2].header[key]
        return pout, outfit, models, 0
    except Exception as E:
        if verb:
            for l in pout:
                print l[:-1]
        if verb:
            print E
        if verb:
            print 'something went wrong...'
        return pout, [-1, -1, -1, -1], [], 1


def sxmsk(scifile, whtfile, pPath, out='tsex', nrem=1, verb=True):
    '''
        Sextractor pass to mask objects that can affect the fit
        Simple approach, almost default config
        nrem is the removal of central object.
            0 means all objects are masked
            1 means only the central object is masked
            2 means central and overlapping objects are masked
        pPath is the location of the sextractor config and params files
    '''
    tcall = 'sex -c {0}galfitmask.sex {1} -CATALOG_NAME {2}.cat -WEIGHT_IMAGE {3} -PARAMETERS_NAME {0}galfitmask.param -FILTER_NAME {0}default.conv -CHECKIMAGE_NAME {2}.fits'.format(
        pPath, scifile, out, whtfile)
    p = Popen(tcall.split(), stdout=PIPE, stderr=PIPE)
    p.wait()
    if verb:
        for l in p.stderr.readlines():
            print l[:-1]
    mskfit = pyfits.open("{0}.fits".format(out))
    amsk = np.ones(mskfit[0].data.shape)
    amsk[mskfit[0].data != 0] = 0
    sexcat = pyfits.open("{0}.cat".format(out))[2].data
    idx = mskfit[0].data[mskfit[0].data.shape[0]/2, mskfit[0].data.shape[1]/2]
    if idx == 0:
        if verb:
            print 'Something wrong here, no object at the center!'
        return np.ones(mskfit[0].shape), [], {}
    '''this is the silliest way to do this'''
    t = []
    for el in np.where(mskfit[0].data.ravel() == idx)[0]:
        elidx = np.unravel_index(el, mskfit[0].data.shape)
        t.extend(mskfit[0].data[elidx[0]-1:elidx[0] +
                                1, elidx[1]-1:elidx[1]+1].ravel())
    t = list(set(t))
    t.remove(idx)
    if 0 in t:
        t.remove(0)
    ''''''
    torem = {0: [], 1: [idx], 2: t}
    models = []
    for i in range(nrem+1):
        for j in torem[i]:
            amsk[mskfit[0].data == j] = 1
            jidx = np.where(sexcat['NUMBER'] == j)[0][0]
            models.append({0: 'sersic', 1: '{0} {1} 1 1'.format(sexcat['X_IMAGE'][jidx], sexcat['Y_IMAGE'][jidx]),
                           3: '{0} 1'.format(sexcat['MAG_AUTO'][jidx]), 4: '{0} 1'.format(sexcat['KRON_RADIUS'][jidx]*sexcat['B_IMAGE'][jidx]),
                           5: '4 1', 9: '{0} 1'.format(sexcat['ELONGATION'][jidx]**-1), 10: '{0} 1'.format(sexcat['THETA_IMAGE'][jidx]-90), 'Z': 0, 'Comment': 'Sersic {0}'.format(i)})
    return amsk, models, torem


def maskfiles(sci, wht, msk, fout=["tsci.fits", "twht.fits"]):
    Popen(["rm", fout[0]], stderr=PIPE)
    Popen(["rm", fout[1]], stderr=PIPE)
    scifits = pyfits.open(sci)
    scifits[0].data *= msk
    scifits.writeto(fout[0], clobber=True)
    whtfits = pyfits.open(wht)
    whtfits[0].data *= msk
    whtfits.writeto(fout[1], clobber=True)
    scifits.close()
    whtfits.close()
    return fout