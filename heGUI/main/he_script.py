


from tifffile import imread
from skimage import io
import numpy as np

from skimage.measure import regionprops
from skimage.measure import label
from skimage.transform import resize

from typing import Dict
from mibitracker.request_helpers import MibiRequests
from FOVlist import Options


def tile(x_0, y_0, xn, yn, fov_size, overlap_x, overlap_y, slideID, sectionID, map_patient, options):
    ''' Using a template json file, creates another fov json that includes
    the tiled version of the original FOV.
    Args:
        fov_list_json_file: The FOV json containing the FOV to be tiled. The
            resulting tiled json is created in the same directory as this file.
        xn: The number of tiles in the x direction.
        yn: The number of tiles in the y direction.
        overlap_x: The degree of overlap between tiles in the x direction.
            Must be between -1 and 1. Negative values result in spacing between
            the FOVs.
        overlap_y: The degree of overlap between tiles in the y direction.
    '''

    
    x = int(x_0)
    y = int(y_0)
    overlap_x_microns = fov_size * overlap_x
    overlap_y_microns = fov_size * overlap_y
    x_ = []
    y_ = []
    for xi in np.arange(xn):
        for yi in np.arange(yn):
            cur_x = x + xi * (fov_size - overlap_x_microns)
            cur_y = y - yi * (fov_size - overlap_y_microns)

            options.add_fov(
                scanCount=1,
                centerPointMicronX=int(cur_x), 
                centerPointMicronY=int(cur_y),
                fovSizeMicrons=fov_size,
                name=f'{map_patient}_{str(int(xi))}_{str(int(yi))}',
                sectionId=sectionID,
                slideId=slideID
                )

            x_.append(cur_x)
            y_.append(cur_y)

    return x_, y_



def transformation(x, y):
    return np.linalg.lstsq(x, y, rcond=None)


##inspired from https://github.com/Jarvis73/Moving-Least-Squares

def mls_affine_deformation(vy, vx, p, q, alpha=1.0, eps=1e-8):
    """
    Affine deformation
    Parameters
    ----------
    vy, vx: ndarray
        coordinate grid, generated by np.meshgrid(gridX, gridY)
    p: ndarray
        an array with size [n, 2], original control points
    q: ndarray
        an array with size [n, 2], final control points
    alpha: float
        parameter used by weights
    eps: float
        epsilon

    Return
    ------
        A deformed image.
    """

    # Change (x, y) to (row, col)
    q = np.ascontiguousarray(q[:, [1, 0]].astype(np.int16))
    p = np.ascontiguousarray(p[:, [1, 0]].astype(np.int16))

    # Exchange p and q and hence we transform destination pixels to the corresponding source pixels.
    p, q = q, p

    grow = vx.shape[0]  # grid rows
    gcol = vx.shape[1]  # grid cols
    ctrls = p.shape[0]  # control points

    # Precompute
    reshaped_p = p.reshape(ctrls, 2, 1, 1)                                              # [ctrls, 2, 1, 1]
    reshaped_v = np.vstack((vx.reshape(1, grow, gcol), vy.reshape(1, grow, gcol)))      # [2, grow, gcol]

    w = 1.0 / (np.sum((reshaped_p - reshaped_v).astype(np.float32) ** 2, axis=1) + eps) ** alpha    # [ctrls, grow, gcol]
    w /= np.sum(w, axis=0, keepdims=True)                                               # [ctrls, grow, gcol]

    pstar = np.zeros((2, grow, gcol), np.float32)
    for i in range(ctrls):
        pstar += w[i] * reshaped_p[i]                                                   # [2, grow, gcol]

    phat = reshaped_p - pstar                                                           # [ctrls, 2, grow, gcol]
    phat = phat.reshape(ctrls, 2, 1, grow, gcol)                                        # [ctrls, 2, 1, grow, gcol]
    phat1 = phat.reshape(ctrls, 1, 2, grow, gcol)                                       # [ctrls, 1, 2, grow, gcol]
    reshaped_w = w.reshape(ctrls, 1, 1, grow, gcol)                                     # [ctrls, 1, 1, grow, gcol]
    pTwp = np.zeros((2, 2, grow, gcol), np.float32)
    for i in range(ctrls):
        pTwp += phat[i] * reshaped_w[i] * phat1[i]
    del phat1

    try:
        inv_pTwp = np.linalg.inv(pTwp.transpose(2, 3, 0, 1))                            # [grow, gcol, 2, 2]
        flag = False
    except np.linalg.linalg.LinAlgError:
        flag = True
        det = np.linalg.det(pTwp.transpose(2, 3, 0, 1))                                 # [grow, gcol]
        det[det < 1e-8] = np.inf
        reshaped_det = det.reshape(1, 1, grow, gcol)                                    # [1, 1, grow, gcol]
        adjoint = pTwp[[[1, 0], [1, 0]], [[1, 1], [0, 0]], :, :]                        # [2, 2, grow, gcol]
        adjoint[[0, 1], [1, 0], :, :] = -adjoint[[0, 1], [1, 0], :, :]                  # [2, 2, grow, gcol]
        inv_pTwp = (adjoint / reshaped_det).transpose(2, 3, 0, 1)                       # [grow, gcol, 2, 2]

    mul_left = reshaped_v - pstar                                                       # [2, grow, gcol]
    reshaped_mul_left = mul_left.reshape(1, 2, grow, gcol).transpose(2, 3, 0, 1)        # [grow, gcol, 1, 2]
    mul_right = np.multiply(reshaped_w, phat, out=phat)                                 # [ctrls, 2, 1, grow, gcol]
    reshaped_mul_right = mul_right.transpose(0, 3, 4, 1, 2)                             # [ctrls, grow, gcol, 2, 1]
    out_A = mul_right.reshape(2, ctrls, grow, gcol, 1, 1)[0]                            # [ctrls, grow, gcol, 1, 1]
    A = np.matmul(np.matmul(reshaped_mul_left, inv_pTwp), reshaped_mul_right, out=out_A)    # [ctrls, grow, gcol, 1, 1]
    A = A.reshape(ctrls, 1, grow, gcol)                                                 # [ctrls, 1, grow, gcol]
    del mul_right, reshaped_mul_right, phat

    # Calculate q
    reshaped_q = q.reshape((ctrls, 2, 1, 1))                                            # [ctrls, 2, 1, 1]
    qstar = np.zeros((2, grow, gcol), np.float32)
    for i in range(ctrls):
        qstar += w[i] * reshaped_q[i]                                                   # [2, grow, gcol]
    del w, reshaped_w

    # Get final image transfomer -- 3-D array
    transformers = np.zeros((2, grow, gcol), np.float32)
    for i in range(ctrls):
        transformers += A[i] * (reshaped_q[i] - qstar)
    transformers += qstar
    del A

    # Correct the points where pTwp is singular
    if flag:
        blidx = det == np.inf    # bool index
        transformers[0][blidx] = vx[blidx] + qstar[0][blidx] - pstar[0][blidx]
        transformers[1][blidx] = vy[blidx] + qstar[1][blidx] - pstar[1][blidx]

    # Removed the points outside the border
    transformers[transformers < 0] = 0
    transformers[0][transformers[0] > grow - 1] = 0
    transformers[1][transformers[1] > gcol - 1] = 0

    return transformers.astype(np.int16)


def get_annotation_coords(target_image):
    '''
    Retrieves the yellow annotation from the target image based on the colour
    :param target_image: H&E image with the annotations
    :return: contours and binary image
    '''
    #get yellow annotaitons based on colour
    new_image = (target_image[..., 0] > 160) * (target_image[..., 1] > 100) * (target_image[..., 2] < 180)
    # skeletonised = skeletonize(new_image > 0)
    label_im = label(new_image.astype(np.uint8))
    regions = regionprops(label_im)
    

    # contours = find_contours(new_image)
    return regions, new_image


def get_corners(regions, n_annots):
    '''
    Get coordinates of the corner right and left of the contours
    :param contours:list of (n,2)-ndarrays
    :return:array of (n,4) with (n,2) top right and (n,2)left corners for each rectangle
    '''
    regions.sort(key=lambda x: x.area, reverse=True)
    regions = regions[:n_annots]
    corners = []
    for region in regions:
        #n = n*2
        x_coord_min = region.coords[:,0].min()
        y_coord_min = region.coords[:,1].min()

        x_coord_max = region.coords[:,0].max()
        y_coord_max = region.coords[:,1].max()

        #filtering out noise
        # if x_coord_max > 5+x_coord_min and y_coord_max > 5+y_coord_min:
        corners.append((x_coord_min, y_coord_min, x_coord_max, y_coord_max))
    
    corners = sorted(corners, key=lambda element: (element[1], element[2]))
    
    return np.array(corners)


def resize_(mov, ref):
    '''
    Resizes images
    :param mov: image destination
    :param ref: reference image to be resized
    :return: ref image matching mov's size
    '''
    return resize(ref, (mov.shape[0], mov.shape[1]))

def align_images(target_image, pts_ref, pts_mov):
    '''
    :param target_image: HE image
    :param pts_ref: reference points on the HE image
    :param pts_mov: moving points
    :return: align HE image to the MIBI image
    '''
    height, width, _ = target_image.shape
    gridX = np.arange(width, dtype=np.int16)
    gridY = np.arange(height, dtype=np.int16)

    vy, vx = np.meshgrid(gridX, gridY)
    affine = mls_affine_deformation(vy, vx, pts_ref, pts_mov, alpha=1)
    transformed_target = np.ones_like(target_image)
    transformed_target[vx, vy] = target_image[tuple(affine)]

    return transformed_target


def def_slide(mibi_tracker_ID: int, login_details: Dict, patient_order: Dict) -> Dict:
    '''
    :param mibi_tracker_ID: ID displayed in the first column in MIBI tracker
    :param login_details: Dictionay containing username, password and backend url
    :param patient_order: Ordering of the annotations in the slide
    :return patient_info: 
    '''
    email = login_details["email"]
    password = login_details["password"]
    BACKEND_URL = login_details["BACKEND_URL"]

    try:
        mr = MibiRequests(BACKEND_URL, email, password)
    except Exception as ex:
        raise Exception("Password or Username is incorrect in dat file")

    single_slide = mr.get('/slides/{}/'.format(mibi_tracker_ID)).json()

    slide_id = single_slide['id']
    section_map_ = {}

    for section in single_slide['sections']:
        name = section['position']
        section_map_[name] = section['id']


    section_map = {}
    for order, name in patient_order.items():
        section_map[order] = section_map_.get(name)

    patient_info = {'slideId': slide_id,
                    'patientMap': patient_order,
                    'sectionMap': section_map}
    print(patient_info)
    return patient_info


def get_fovs(transformed_FOV_min, patient_info, fov_size, FOV_grid):
    '''
    :param transformed_FOV_min:
    :param patient_info:
    :param fov_size:
    :param FOV_grid:
    :return:
    '''
    final_x = np.empty(1)
    final_y = np.empty(1)
    assert transformed_FOV_min.shape[0] == len(patient_info['sectionMap']), 'There are more regions selected than patient, review your selections'
    
    options = Options()
    for i in range(len(patient_info['sectionMap'])):

        x_0 = transformed_FOV_min[i, 0] + fov_size/2
        y_0 = transformed_FOV_min[i, 1] - fov_size/2
        xn = FOV_grid[i, 0]
        yn = FOV_grid[i, 1]
        overlap_x = 0.1
        overlap_y = 0.1
        sectionID = patient_info['sectionMap'][i]
        slideID = patient_info['slideId']
        patient_map = patient_info['patientMap'][i]

        
        x, y = tile(x_0, y_0, xn, yn, fov_size, overlap_x, overlap_y, slideID, sectionID, patient_map, options)
        

        final_x = np.append(final_x, x)
        final_y = np.append(final_y, y)
    
    
    return final_x, final_y, options
