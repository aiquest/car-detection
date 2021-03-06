import sys
# Ensure that the cardetection package is on the Python path.
sys.path.append('../../')

import os
import os.path
import pprint
import flask
from flask import render_template
from flask import request
from flask import jsonify
import cv2
import cardetection.carutils.images as utils
import cardetection.carutils.fileutils as fileutils
from cardetection.detection.detector import ObjectDetector

app = flask.Flask(__name__)

# Generate secret key for security.
# Note: This will invalidate sessions if the app restarts, but that doesn't
# matter for this research/demo app.
# See: http://stackoverflow.com/q/27287391/3622526
# See: http://flask.pocoo.org/docs/0.10/quickstart/#sessions
import os
app.secret_key = os.urandom(24)
app.debug = False # Debug must be false if we're serving to the Internet.

# TODO: Consider using the methods here if more configuration is required in the
# future.
# http://flask.readthedocs.org/en/0.6/config/


detector_config_fname = os.path.join(app.instance_path, 'detector-config.yaml')
if __name__ == '__main__':
    detector_config_fname = os.path.join(app.instance_path, 'detector-config-local.yaml')


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/_add_numbers', methods=['POST'])
def add_numbers():
    """Add two numbers server side, ridiculous but well..."""
    a = request.json['a']
    b = request.json['b']
    return jsonify(result=a + b)

def url_safe_hash(value):
    import base64
    hashed_value = base64.urlsafe_b64encode(repr(hash(value)))
    return hashed_value

def hash_config_values(config_yaml):
    hashed_config = []
    for entry in config_yaml:
        value = entry['value']
        label = entry['label']
        if isinstance(value, (list, tuple)):
            value = tuple(value)

        hashed_value = url_safe_hash(value)
        hashed_config.append({'value': hashed_value, 'label': label})
    return hashed_config
def hashed_config_value_dict(config_yaml):
    hashed_dict = {}
    for entry in config_yaml:
        print entry
        value = entry['value']
        label = entry['label']
        if isinstance(value, (list, tuple)):
            value = tuple(value)
        hashed_value = url_safe_hash(value)
        hashed_dict[hashed_value] = value
    return hashed_dict

def hashed_value_is_in_config_values(value, config_yaml):
    hashed_config = hash_config_values(config_yaml)
    values = [entry['value'] for entry in hashed_config]
    return value in values

@app.route('/_detector_directories', methods=['GET'])
def detector_directories():
    """Load the detector directories from the config file"""
    config_yaml = fileutils.load_yaml_file(detector_config_fname)
    hashed_config = hash_config_values(config_yaml['detector_directories'])
    return jsonify(detector_directories=hashed_config)
@app.route('/_image_directories', methods=['GET'])
def image_directories():
    """Load the image directories from the config file"""
    config_yaml = fileutils.load_yaml_file(detector_config_fname)
    hashed_config = hash_config_values(config_yaml['image_directories'])
    return jsonify(image_directories=hashed_config)

def validate_image_directory(image_dir, config_yaml):
    img_dir_config = config_yaml['image_directories']
    # Ensure that only the allowed image directories are accessed:
    # allowed_img_dirs = [entry['value'] for entry in config_yaml['image_directories']]
    # if not image_dir in allowed_img_dirs:
    if not hashed_value_is_in_config_values(image_dir, img_dir_config):
        print 'ERROR: The directory \'{}\' is not in the list of image directories.'.format(image_dir)
        # Indicate that this isn't allowed.
        # TODO: Display a better error to the client.
        flask.abort(403) # HTTP status codes: Forbidden
    return hashed_config_value_dict(img_dir_config)[image_dir]
def validate_detector_directory(detector_dir, config_yaml):
    detector_dir_config = config_yaml['detector_directories']
    # Ensure that only the allowed detector directories are accessed:
    # allowed_detector_dirs = [entry['value'] for entry in config_yaml['detector_directories']]
    # if not detector_dir in allowed_detector_dirs:
    if not hashed_value_is_in_config_values(detector_dir, detector_dir_config):
        print 'ERROR: The directory \'{}\' is not in the list of detector directories.'.format(detector_dir)
        # Indicate that this isn't allowed.
        # TODO: Display a better error to the client.
        flask.abort(403) # HTTP status codes: Forbidden
    return hashed_config_value_dict(detector_dir_config)[detector_dir]

@app.route('/_update_preview_state', methods=['POST'])
def update_preview_state():
    """Return the new state of the UI given the new settings."""
    print 'update_preview_state'

    print 'request data:'
    pprint.pprint(request.json)

    # Get the inputs:
    currentImgIndex = request.json['currentImgIndex']
    hashed_image_dir = request.json['imageDir']
    hashed_detector_dir = request.json['detectorDir']
    performDetection = request.json['performDetection']
    returnImage = request.json['returnImage']

    config_yaml = fileutils.load_yaml_file(detector_config_fname)

    imageDir = validate_image_directory(hashed_image_dir, config_yaml)

    # Get the images:
    image_list = sorted(utils.list_images_in_directory(imageDir))
    num_images = len(image_list)

    if num_images == 0:
        print 'ERROR: The directory \'{}\' contains no images.'.format(imageDir)
        # TODO: Display a better error to the client.
        flask.abort(404) # HTTP status codes: Not Found

    # Find the current image:
    if not currentImgIndex:
        currentImgIndex = 0
    current_img_index = currentImgIndex % num_images
    current_img_path = image_list[current_img_index]
    send_img_path = current_img_path

    # Perform detection:
    detections = []
    if performDetection:
        save_img_dir = os.path.join(app.root_path, 'static', 'cache')
        save_img_fname = '{}.jpg'.format(url_safe_hash(current_img_path + hashed_detector_dir))
        save_img_path = os.path.join(save_img_dir, save_img_fname)
        send_img_path = save_img_path
        detection_img_exists = os.path.isfile(save_img_path)
        # if not returnImage and detection_img_exists:
        #     # Delete the current image so that it isn't returned by mistake if
        #     # the detection process fails.
        #     os.remove(save_img_path)
        if not returnImage or not detection_img_exists:
            # Perform the detection.

            detectorDir = validate_detector_directory(hashed_detector_dir, config_yaml)

            # detector = ObjectDetector.load_from_directory(detectorDir)
            with ObjectDetector(detectorDir) as detector:
                img = cv2.imread(current_img_path)
                detections, img = detector.detect_objects_in_image(img)

                # cv2.imwrite fails silently if it can't save the image for any
                # reason. We manually check access permissions here, and throw
                # an exception to inform the webmaster if they're incorrect.
                sav_img_dir, _ = os.path.split(save_img_path)
                if not os.path.isdir(sav_img_dir):
                    raise IOError('The sav_img_dir \'{}\' does not exist.'.format(sav_img_dir))
                if not os.access(sav_img_dir, os.W_OK):
                    raise IOError('The server user (probably www-data) does not have write permissions for the save_img_path: \'{sav_img_dir}\''.format(sav_img_dir))
                cv2.imwrite(save_img_path, img)

    previewState = jsonify({
        'numImages' : num_images,
        'currentImgIndex' : current_img_index,
        'currentImgPath' : current_img_path,
        # 'currentImgUrl' : None,
        'detections' : detections
    })

    if returnImage:
        print 'preview state:', previewState.data
        # Return the image
        return flask.send_file(send_img_path)
    else:
        # Return the new preview state:
        print 'response data:', previewState.data
        return previewState



if __name__ == '__main__':
    # Start a local development server.
    # Note: This is not run when serving on apache.
    # http://flask.pocoo.org/docs/0.10/deploying/mod_wsgi/#creating-a-wsgi-file
    app.run(debug=True)
