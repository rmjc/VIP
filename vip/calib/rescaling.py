#! /usr/bin/env python

"""
Module with frame resampling/rescaling functions.
"""
__author__ = 'C. Gomez @ ULg, V. Christiaens @ ULg'
__all__ = ['frame_px_resampling',
           'cube_px_resampling',
           'scale_cube',
           'frame_rescaling',
           'cube_rescaling',
           'check_scal_vector']

import cv2
import numpy as np
from scipy.ndimage.interpolation import geometric_transform
from ..var import frame_center, get_square_robust



def frame_px_resampling(array, scale, interpolation='bicubic'):
    """ Resamples the pixels of a frame wrt to the center, changing the size
    of the frame. If 'scale' < 1 then the frame is downsampled and if 
    'scale' > 1 then its pixels are upsampled. Uses opencv for maximum speed. 
    Several modes of interpolation are available. 
    
    Parameters
    ----------
    array : array_like 
        Input frame, 2d array.
    scale : float
        Scale factor for upsampling or downsampling the frame.
    interpolation : {'bicubic', 'bilinear', 'nearneig'}, optional
        'nneighbor' stands for nearest-neighbor interpolation,
        'bilinear' stands for bilinear interpolation,
        'bicubic' for interpolation over 4x4 pixel neighborhood.
        The 'bicubic' is the default. The 'nearneig' is the fastest method and
        the 'bicubic' the slowest of the three. The 'nearneig' is the poorer
        option for interpolation of noisy astronomical images. 
        Even with 'bicubic' interpolation, opencv library is several orders of
        magnitude faster than python similar functions (e.g. ndimage).
        
    Returns
    -------
    array_resc : array_like 
        Output resampled frame.
    """
    if not array.ndim == 2:
        raise TypeError('Input array is not a frame or 2d array.')
    
    if interpolation == 'bilinear':
        intp = cv2.INTER_LINEAR
    elif interpolation == 'bicubic':
        intp= cv2.INTER_CUBIC
    elif interpolation == 'nearneig':
        intp = cv2.INTER_NEAREST
    else:
        raise TypeError('Interpolation method not recognized.')
    
    array_resc = cv2.resize(array.astype(np.float32), (0,0), fx=scale, 
                            fy=scale, interpolation=intp)
    return array_resc



def cube_px_resampling(array, scale, interpolation='bicubic'):
    """ Wrapper of frame_px_resample() for resampling the frames of a cube with
    a single scale. Useful when we need to upsample (upsacaling) or downsample 
    (pixel binning) a set of frames, e.g. an ADI cube. 
    
    Parameters
    ----------
    array : array_like 
        Input frame, 2d array.
    scale : float
        Scale factor for upsampling or downsampling the frames in the cube.
    interpolation : {'bicubic', 'bilinear', 'nearneig'}, optional
        'nneighbor' stands for nearest-neighbor interpolation,
        'bilinear' stands for bilinear interpolation,
        'bicubic' for interpolation over 4x4 pixel neighborhood.
        The 'bicubic' is the default. The 'nearneig' is the fastest method and
        the 'bicubic' the slowest of the three. The 'nearneig' is the poorer
        option for interpolation of noisy astronomical images. 
        Even with 'bicubic' interpolation, opencv library is several orders of
        magnitude faster than python similar functions (e.g. ndimage).
        
    Returns
    -------
    array_resc : array_like 
        Output cube with resampled frames.
    """
    if not array.ndim==3:
        raise TypeError('Input array is not a cube or 3d array.')
    
    array_resc = np.zeros((array.shape[0], int(array.shape[1]*scale), 
                           int(array.shape[2]*scale)))
    for i in range(array.shape[0]):
        array_resc[i] = frame_px_resampling(array[i], scale=scale, 
                                            interpolation=interpolation)
    return array_resc



# TODO: to move this function to PCA module
def scale_cube(cube,scal_list,full_output=True,inverse=False,y_in=1,x_in=1):
    """
    Wrapper to scale or descale a cube by factors given in scal_list, without 
    any loss of information (zero-padding if scaling > 1).
    Important: in case of ifs data, the scaling factors in var_list should be 
    >= 1 (ie. provide the scaling factors as for scaling to the longest 
    wavelength channel)

    Parameters:
    -----------
    cube: 3D-array
       Datacube that whose frames have to be rescaled
    scal_list: 1D-array
       Vector of same dimension as the first dimension of datacube, containing 
       the scaling factor for each frame.
    full_output: bool, {True,False}, optional
       Whether to output just the rescaled cube (False) or also its median, 
       the new y and x shapes of the cube, and the new centers cy and cx of the 
       frames (True).
    inverse: bool, {True,False}, optional
       Whether to inverse the scaling factors in scal_list before applying them 
       or not; i.e. True is to descale the cube (typically after a first scaling
       has already been done)
    y_in, x-in:
       Initial y and x sizes.
       In case the cube is descaled, these values will be used to crop back the
       cubes/frames to their original size.

    Returns:
    --------
    frame: 2D-array
        The median of the rescaled cube.
    If full_output is set to True, the function returns:
    cube,frame,y,x,cy,cx: 3D-array,2D-array,int,int,int,int
        The rescaled cube, its median, the new y and x shapes of the cube, and 
        the new centers cy and cx of the frames
    """
    #First pad the cube with zeros appropriately to not loose info when scaling
    # the cube.
    # TBD next: pad with random gaussian noise instead of zeros. Padding with 
    # only zeros can make the svd not converge in a pca per zone.

    n, y, x = cube.shape

    max_sc = np.amax(scal_list)

    if not inverse and max_sc > 1:
        new_y = np.ceil(max_sc*y)
        new_x = np.ceil(max_sc*x)
        if (new_y - y)%2 != 0: new_y = new_y+1
        if (new_x - x)%2 != 0: new_x = new_x+1
        pad_len_y = (new_y - y)/2
        pad_len_x = (new_x - x)/2
        big_cube = np.pad(cube, ((0,0), (pad_len_y, pad_len_y), 
                                 (pad_len_x, pad_len_x)), 'constant', 
                          constant_values=(0,))
    else: 
        big_cube = cube.copy()

    n, y, x = big_cube.shape
    cy,cx = frame_center(big_cube[0])
    var_list = scal_list

    if inverse:
        var_list = 1./scal_list[:]
        cy,cx = frame_center(cube[0])

    # (de)scale the cube, so that a planet would now move radially
    cube,frame = cube_rescaling(big_cube,var_list,ref_y=cy, ref_x=cx)

    if inverse:
        if max_sc > 1:
            frame = get_square_robust(frame,max(y_in,x_in), cy,cx,strict=False)
            if full_output:
                n_z = cube.shape[0]
                array_old = cube.copy()
                cube = np.zeros([n_z,max(y_in,x_in),max(y_in,x_in)])
                for zz in range(n_z):
                    cube[zz]=get_square_robust(array_old[zz],max(y_in,x_in), 
                                               cy,cx,strict=False)


    if full_output: return cube,frame,y,x,cy,cx
    else: return frame



def frame_rescaling(array, ref_y=None, ref_x=None, scale=1.0, 
                    method='geometric_transform'):
    """
    Function to rescale a frame by a factor 'scale', wrt a reference point 
    ref_pt which by default is the center of the frame (typically the exact 
    location of the star). However, it keeps the same dimensions. It uses spline 
    interpolation of order 3 to find the new values in the output array.
    
    Parameters
    ----------
    array : array_like 
        Input frame, 2d array.
    ref_y, ref_x : float, optional
        Coordinates X,Y  of the point with respect to which the rotation will be
        performed. By default the rotation is done with respect to the center 
        of the frame; central pixel if frame has odd size.
    scale : float
        Scaling factor. If > 1, it will upsample the input array.        
    method: string, {'geometric_transform','cv2.warp_affine'}, optional
        String determining which library to apply to rescale. 
        Both options use a spline of order 3 for interpolation.
        Opencv is a few order of magnitudes faster than ndimage.

    Returns
    -------
    array_out : array_like
        Resulting frame.
    """
    def _scale_func(output_coords,ref_y=0,ref_x=0, scaling=1.0):    
        """
        For each coordinate point in a new scaled image (output_coords), 
        coordinates in the image before the scaling are returned. 
        This scaling function is used within geometric_transform (in 
        frame_rescaling), 
        which, for each point in the output image, will compute the (spline)
        interpolated value at the corresponding frame coordinates before the 
        scaling.
        """
        return (ref_y+((output_coords[0]-ref_y)/scaling), 
                ref_x+((output_coords[1]-ref_x)/scaling))

    array_out = np.zeros_like(array)
    
    if not ref_y and not ref_x:  ref_y, ref_x = frame_center(array)

    if method == 'geometric_transform':
        geometric_transform(array, _scale_func, output_shape=array.shape, 
                            output = array_out, 
                            extra_keywords={'ref_y':ref_y,'ref_x':ref_x,
                                            'scaling':scale})

    elif method == 'cv2.warp_affine':
        M = np.array([[scale,0,(1.-scale)*ref_x],[0,scale,(1.-scale)*ref_y]])
        array_out = cv2.warpAffine(array.astype(np.float32), M, 
                                   (array.shape[1], array.shape[0]), 
                                   flags=cv2.INTER_LINEAR)

    else:
        msg="Pick a valid method: 'geometric_transform' or 'cv2.warp_affine'"
        raise ValueError(msg)

    return array_out

    
    
def cube_rescaling(array, scaling_list, ref_y=None, ref_x=None, 
                   method='cv2.warp_affine'):
    """ 
    Function to rescale a cube, frame by frame, by a factor 'scale', with 
    respect to position (cy,cx). It calls frame_rescaling function.
    
    Parameters
    ----------
    array : array_like 
        Input 3d array, cube.
    scaling_list : 1D-array
        Scale corresponding to each frame in the cube.
    ref_y, ref_x : float, optional
        Coordinates X,Y  of the point with respect to which the rescaling will be
        performed. By default the rescaling is done with respect to the center 
        of the frames; central pixel if the frames have odd size.
    method: {'cv2.warp_affine', 'geometric_transform'}, optional
        String determining which library to apply to rescale. 
        Both options use a spline of order 3 for interpolation.
        Opencv is a few order of magnitudes faster than ndimage.
        
    Returns
    -------
    array_sc : array_like
        Resulting cube with rescaled frames.
    array_out : array_like
        Median combined image of the rescaled cube.
    """
    if not array.ndim == 3:
        raise TypeError('Input array is not a cube or 3d array.')
    array_sc = np.zeros_like(array) 
    
    if not ref_y and not ref_x:  ref_y, ref_x = frame_center(array[0])
    
    for i in xrange(array.shape[0]): 
        array_sc[i] = frame_rescaling(array[i], ref_y=ref_y, ref_x=ref_x, 
                                      gamma=scaling_list[i], method=method)
            
    array_out = np.median(array_sc, axis=0)              
    return array_sc, array_out


def check_scal_vector(scal_vec):
    """
    Function to check if the scaling list has the right format to avoid any bug
    in the pca algorithm, in the case of ifs data.
    Indeed, all scaling factors should be >= 1 (i.e. the scaling should be done
    to match the longest wavelength of the cube)

    Parameter:
    ----------
    scal_vec: array_like, 1d OR list

    Returns:
    --------
    scal_vec: array_like, 1d 
        Vector containing the scaling factors (after correction to comply with
        the condition >= 1)

    """
    correct = False

    if isinstance(scal_vec, list):
        scal_list = scal_vec.copy()
        nz = len(scal_list)
        scal_vec = np.zeros(nz)
        for ii in range(nz):
            scal_vec[ii] = scal_list[ii]
        correct = True
    elif isinstance(scal_vec,np.ndarray):
        nz = scal_vec.shape[0]
    else:
        raise TypeError('scal_vec is neither a list or an np.ndarray')

    scal_min = np.amin(scal_vec)

    if scal_min < 1:
        correct = True

    if correct:
        for ii in range(nz):
            scal_vec[ii] = scal_vec[ii]/scal_min

    return scal_vec

