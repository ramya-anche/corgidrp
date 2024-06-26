# Place to put detector-related utility functions

import numpy as np
import corgidrp.data as data
from scipy import interpolate
from astropy.time import Time

def create_dark_calib(dark_dataset):
    """
    Turn this dataset of image frames that were taken to measure
    the dark current into a dark calibration frame and determines the corresponding error

    Args:
        dark_dataset (corgidrp.data.Dataset): a dataset of Image frames (L2a-level)

    Returns:
        data.Dark: a dark calibration frame
    """
    combined_frame = np.nanmean(dark_dataset.all_data, axis=0)

    new_dark = data.Dark(combined_frame, pri_hdr=dark_dataset[0].pri_hdr.copy(),
                         ext_hdr=dark_dataset[0].ext_hdr.copy(), input_dataset=dark_dataset)
    
    # determine the standard error of the mean: stddev/sqrt(n_frames)
    new_dark.err = np.nanstd(dark_dataset.all_data, axis=0)/np.sqrt(len(dark_dataset))
    new_dark.err = new_dark.err.reshape((1,)+new_dark.err.shape) #Get it into the right dimensions

    return new_dark

def create_flatfield(flat_dataset):
    
    """
    Turn this dataset of image frames that were taken for performing the flat calibration and
    to make one master flat image
    this is currently a placeholder, until the final flat fielding calibration package is completed. 

    Args:
       flat_dataset (corgidrp.data.Dataset): a dataset of Image frames (L2a-level)

    Returns:
        data.masterflat: a master flat for flat calibration
    """  
    
    
    combined_frame = np.nanmean(flat_dataset.all_data, axis=0)
 
    flat_field = data.FlatField(combined_frame, pri_hdr=flat_dataset[0].pri_hdr.copy(),
                         ext_hdr=flat_dataset[0].ext_hdr.copy(), input_dataset=flat_dataset)
    
    #determine the standard error of the mean: stddev/sqrt(n_frames)
    flat_field.err = np.nanstd(flat_dataset.all_data, axis=0)/np.sqrt(len(flat_dataset))
    flat_field.err=flat_field.err.reshape((1,)+flat_field.err.shape) # Get it into the right dimension

    
    return flat_field

def get_relgains(frame, em_gain, non_lin_correction):
    """
    For a given bias subtracted frame of dn counts, return a same sized
    array of relative gain values.

    This algorithm contains two interpolations:

    - A 2d interpolation to find the relative gain curve for a given EM gain
    - A 1d interpolation to find a relative gain value for each given dn
      count value.

    Both of these interpolations are linear, and both use their edge values as
    constant extrapolations for out of bounds values.

    Parameters:
        frame (array_like): Array of dn count values.
        em_gain (float): Detector EM gain.
        non_lin_correction (corgi.drp.NonLinearityCorrection): A NonLinearityCorrection calibration file.

    Returns:
        array_like: Array of relative gain values.
    """

    # Column headers are gains, row headers are dn counts
    gain_ax = non_lin_correction.data[0, 1:]
    count_ax = non_lin_correction.data[1:, 0]
    # Array is relative gain values at a given dn count and gain
    relgains = non_lin_correction.data[1:, 1:]

    #MMB Note: This check is maybe better placed in the code that is saving the non-linearity correction file?
    # Check for increasing axes
    if np.any(np.diff(gain_ax) <= 0):
        raise ValueError('Gain axis (column headers) must be increasing')
    if np.any(np.diff(count_ax) <= 0):
        raise ValueError('Counts axis (row headers) must be increasing')
    # Check that curves (data in columns) contain or straddle 1.0
    if (np.min(relgains, axis=0) > 1).any() or \
       (np.max(relgains, axis=0) < 1).any():
        raise ValueError('Gain curves (array columns) must contain or '
                              'straddle a relative gain of 1.0')

    # Create interpolation for em gain (x), counts (y), and relative gain (z).
    # Note that this defaults to using the edge values as fill_value for
    # out of bounds values (same as specified below in interp1d)
    f = interpolate.RectBivariateSpline(gain_ax,
                                    count_ax,
                                    relgains.T,
                                    kx=1,
                                    ky=1,
    )
    # Get the relative gain curve for the given gain value
    relgain_curve = f(em_gain, count_ax)[0]

    # Create interpolation for dn counts (x) and relative gains (y). For
    # out of bounds values use edge values
    ff = interpolate.interp1d(count_ax, relgain_curve, kind='linear',
                              bounds_error=False,
                              fill_value=(relgain_curve[0], relgain_curve[-1]))
    # For each dn count, find the relative gain
    counts_flat = ff(frame.ravel())

    return counts_flat.reshape(frame.shape)

detector_areas= {
    'SCI' : {
        'frame_rows' : 1200,
        'frame_cols' : 2200,
        'image' : {
            'rows': 1024,
            'cols': 1024,
            'r0c0': [13, 1088]
            },
        'prescan' : {
            'rows': 1200,
            'cols': 1088,
            'r0c0': [0, 0]
            },
        'prescan_reliable' : {
            'rows': 1200,
            'cols': 200,
            'r0c0': [0, 800]
            },
        'parallel_overscan' : {
            'rows': 163,
            'cols': 1056,
            'r0c0': [1037, 1088]
            },
        'serial_overscan' : {
            'rows': 1200,
            'cols': 56,
            'r0c0': [0, 2144]
            },
        },
    'ENG' :{
        'frame_rows' : 2200,
        'frame_cols' : 2200,
        'image' : {
            'rows': 1024,
            'cols': 1024,
            'r0c0': [13, 1088]
            },
        'prescan' : {
            'rows': 2200,
            'cols': 1088,
            'r0c0': [0, 0]
            },
        'prescan_reliable' : {
            'rows': 2200,
            'cols': 200,
            'r0c0': [0, 800]
            },
        'parallel_overscan' : {
            'rows': 1163,
            'cols': 1056,
            'r0c0': [1037, 1088]
            },
        'serial_overscan' : {
            'rows': 2200,
            'cols': 56,
            'r0c0': [0, 2144]
            },
        },
    }

def slice_section(frame, obstype, key):
    """
    Slice 2d section out of frame

    Args:
        frame (np.ndarray): Full frame consistent with size given in frame_rows, frame_cols
        obstype (str): Keyword referencing the observation type (e.g. 'ENG' or 'SCI')
        key (str): Keyword referencing section to be sliced; must exist in detector_areas

    Returns:
        np.ndarray: a 2D array of the specified detector area
    """
    rows = detector_areas[obstype][key]['rows']
    cols = detector_areas[obstype][key]['cols']
    r0c0 = detector_areas[obstype][key]['r0c0']

    section = frame[r0c0[0]:r0c0[0]+rows, r0c0[1]:r0c0[1]+cols]
    if section.size == 0:
        raise Exception('Corners invalid. Tried to slice shape of {0} from {1} to {2} rows and {3} columns'.format(frame.shape, r0c0, rows, cols))
    return section

def plot_detector_areas(detector_areas, areas=('image', 'prescan',
        'prescan_reliable', 'parallel_overscan', 'serial_overscan')):
    """
    Create an image of the detector areas for visualization and debugging

    Args:
        detector_areas (dict): a dictionary of image constants
        areas (tuple): a tuple of areas to create masks for

    Returns:
        np.ndarray: an image of the detector areas
    """
    detector_areas = make_detector_areas(detector_areas, areas=areas)
    detector_area_image = np.zeros(
        (detector_areas['frame_rows'], detector_areas['frame_cols']), dtype=int)
    for i, area in enumerate(areas):
        detector_area_image[detector_areas[area]] = i + 1
    return detector_area_image

def detector_area_mask(detector_areas, area='image'):
    """
    Create a mask for the detector area

    Args:
        detector_areas (dict): a dictionary of image constants
        area (str): the area of the detector to create a mask for

    Returns:
        np.ndarray: a mask for the detector area
    """
    mask = np.zeros((detector_areas['frame_rows'], detector_areas['frame_cols']), dtype=bool)
    mask[detector_areas[area]['r0c0'][0]:detector_areas[area]['r0c0'][0] + detector_areas[area]['rows'],
            detector_areas[area]['r0c0'][1]:detector_areas[area]['r0c0'][1] + detector_areas[area]['cols']] = True
    return mask

def make_detector_areas(detector_areas, areas=('image', 'prescan', 'prescan_reliable',
        'parallel_overscan', 'serial_overscan')):
    """
    Create a dictionary of masks for the different detector areas

    Args:
        detector_areas (dict): a dictionary of image constants
        areas (tuple): a tuple of areas to create masks for

    Returns:
        dict: a dictionary of masks for the different detector areas
    """
    detector_areas = {}
    for area in areas:
        detector_areas[area] = detector_area_mask(detector_areas, area=area)
    return detector_areas

def get_rowreadtime_sec(datetime=None):
    """
    Get the value of readrowtime. The EMCCD is considered sensitive to the
    effects of radiation damage and, if this becomes a problem, one of the
    mitigation techniques would be to change the row read time to reduce the
    impact of charge traps.
 
    There’s no formal plan/timeline for this adjustment, though it is possible
    to change in the future should it need to.

    Its default value is 223.5e-6 sec.

    Args:
        datetime (astropy Time object): Observation's starting date. Its default
        value is sometime between the first collection of ground data (Full
        Functional Tests) and the duration of the Roman Coronagraph mission.

    Returns:
        rowreadtime (float): Current value of rowreadtime in sec.

    """ 
    # Some datetime between the first collection of ground data (Full
    # Functional Tests) and the duration of the Roman Coronagraph mission.
    if datetime is None:
        datetime = Time('2024-03-01 00:00:00', scale='utc')

    # IIT datetime
    datetime_iit = Time('2023-11-01 00:00:00', scale='utc')
    # Date well in the future to always fall in this case, unless rowreadtime
    # gets updated. One may add more datetime_# values to keep track of changes.
    datetime_1 = Time('2040-01-01 00:00:00', scale='utc')
    
    if datetime < datetime_iit:
        raise ValueError('The observation datetime cannot be earlier than first collected data on ground.')
    elif datetime < datetime_1:
        rowreadtime_sec = 223.5e-6
    else:
        raise ValueError('The observation datetime cannot be later than the' + \
            ' end of the mission')

    return rowreadtime_sec
