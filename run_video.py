import sys
import cv2
import gc
import os
from sys import platform
import argparse
import time
import logging
import subprocess
import numpy as np
import pandas as pd
from logging import getLogger, StreamHandler, Formatter
from modules.motion_analysis import MotionAnalysis
from modules.track_humans import TrackHumans

# Import Openpose (Windows/Ubuntu/OSX)
dir_path = "./" #os.path.dirname(os.path.realpath(__file__))
try:
    # Windows Import
    if platform == "win32":
        # Change these variables to point to the correct folder (Release/x64 etc.)
        sys.path.append(dir_path + '/../../python/openpose/Release');
        os.environ['PATH'] = os.environ['PATH'] + ';' + dir_path + '/../../x64/Release;' + dir_path + '/../../bin;'
        import pyopenpose as op
    else:
        # Change these variables to point to the correct folder (Release/x64 etc.)
        sys.path.append('../../python');
        # If you run `make install` (default path is `/usr/local/python` for Ubuntu), you can also access the OpenPose/python module from there. This will install OpenPose and the python library at your desired installation path. Ensure that this is in your python path in order to use it.
        # sys.path.append('/usr/local/python')
        from openpose import pyopenpose as op
except ImportError as e:
    print(
        'Error: OpenPose library could not be found. Did you enable `BUILD_PYTHON` in CMake and have this Python script in the right folder?')
    raise e


def run_video(video, path='', resize='432x368', model='cmu', resize_out_ratio=4.0, orientation='horizontal',
                   cog="skip", cog_color='black', cog_size='M', showBG=True, start_frame=0, debug=False, plot_image=""):
    start_frame=0
    logger = getLogger("APP_LOG")
    stream_handler = StreamHandler()
    if debug:
        logger.setLevel(logging.DEBUG)
        stream_handler.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        stream_handler.setLevel(logging.INFO)
    handler_format = Formatter('%(name)s, %(levelname)s:\t%(message)s')
    stream_handler.setFormatter(handler_format)
#     logger.addHandler(stream_handler)

    # setting directories to output
    path_movie_out = os.path.join(path, 'movies_estimated')
    path_csv_estimated = os.path.join(path, 'data_estimated')
    path_png_estimated = os.path.join(path, 'png_estimated')
    csv_file = os.path.join(path_csv_estimated, video.rsplit('.')[0] + '.csv')
    os.makedirs(path_movie_out, exist_ok=True)
    os.makedirs(path_png_estimated, exist_ok=True)
    os.makedirs(path_csv_estimated, exist_ok=True)

    # Custom Params (refer to include/openpose/flags.hpp for more parameters)
    params = dict()
    params["model_folder"] = "../../../models/"

    # Starting OpenPose
    opWrapper = op.WrapperPython()
    opWrapper.configure(params)
    opWrapper.start()

    # open video
    cap = cv2.VideoCapture(os.path.join(path, 'movies', video))
    logger.info("OPEN: %s" % video)
    if cap.isOpened() is False:
        logger.info("ERROR: opening video stream or file")
    caps_fps = cap.get(cv2.CAP_PROP_FPS)
    ma = MotionAnalysis()
    track = TrackHumans(start_frame=start_frame)

    # processing video
    frame_no = 0
    # cmap = plt.get_cmap("tab10")
    while cap.isOpened():
        ret_val, image = cap.read()
        if not ret_val:
            break
        if frame_no == 0:
            h_pxl, w_pxl = image.shape[0], image.shape[1]

        # estimate pose
        t = time.time()
        datum = op.Datum()
#         imageToProcess = cv2.imread(image)
        datum.cvInputData = image  # imageToProcess
        opWrapper.emplaceAndPop([datum])
        time_estimation = time.time() - t
        # keypoints
        humans = datum.poseKeypoints

        # calculate cog
        t = time.time()
        bodies_cog = ma.multi_bodies_cog(humans=humans)
        bodies_cog[np.isnan(bodies_cog[:, :, :])] = 0
        # calculate track
        track.track_humans(frame_no, humans)
        humans_feature = np.concatenate((track.humans_current,
                                         bodies_cog.reshape(bodies_cog.shape[0],
                                                            bodies_cog.shape[1] * bodies_cog.shape[2])), axis=1)
        df_frame = pd.DataFrame(humans_feature.round(4))
        df_frame.to_csv(csv_file, index=False, header=None, mode='a')
        time_cog = time.time() - t
        if frame_no % int(caps_fps) == 0:
            logger.info('calculation of cog in %.4f seconds.' % time_cog)

        # check the time to estimation
        if (frame_no % int(caps_fps)) == 0:
            logger.info("Now estimating at:" + str(int(frame_no / caps_fps)) + "[sec]")
            logger.info('inference in %.4f seconds.' % time_estimation)
            logger.debug('shape of image: ' + str(image.shape))
            logger.debug(str(humans))

        img = datum.cvOutputData
        for i in range(len(bodies_cog)):
            cv2.circle(img, (int(bodies_cog[i, 14, 0]), int(bodies_cog[i, 14, 1])), 5, color=(0, 0, 0), thickness=-1)
        #     plt.vlines(bodies_cog[:, 6, 0] * w_pxl, ymin=0, ymax=h_pxl, linestyles='dashed')
        #     plt.vlines(bodies_cog[:, 7, 0] * w_pxl, ymin=0, ymax=h_pxl, linestyles='dashed')

        for i, hum in enumerate(np.sort(track.humans_id)):
            df_human = track.humans_tracklet[track.humans_tracklet[:, track.clm_num] == hum]
            trajectories = np.array([(int(gdf[4 * 3 + 1]), int(gdf[4 * 3 + 2])) for gdf in df_human])
            cv2.polylines(img, [trajectories], False, (0,0,0), 3, cv2.LINE_4)
            trajectories = np.array([(int(gdf[7 * 3 + 1]), int(gdf[7 * 3 + 2])) for gdf in df_human])
            cv2.polylines(img, [trajectories], False, (0,0,0), 3, cv2.LINE_4)

        cv2.imwrite(os.path.join(path_png_estimated,
                                 video.split('.')[-2] + '{:06d}'.format(frame_no) + ".png"), img)

        # before increment, renew some args
        frame_no += 1
        gc.collect()
        if cv2.waitKey(1) == 27:
            break
    cv2.destroyAllWindows()
    logger.info("finish estimation & start encoding")
    cmd = ["ffmpeg", "-r", str(caps_fps), "-start_number", str(start_frame),
           "-i", os.path.join(path_png_estimated, video.split('.')[-2] + "%06d.png"),
           "-vcodec", "libx264", "-pix_fmt", "yuv420p",
           os.path.join(path_movie_out, video.split('.')[-2] + "_track.mp4")]
    subprocess.call(cmd)
    logger.debug('finished+')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='tf-pose-estimation Video')
    parser.add_argument('--path', type=str, default="")
    parser.add_argument('--video', type=str, default='')
    parser.add_argument('--resize', type=str, default='0x0', help='network input resize. default=432x368')
    parser.add_argument('--model', type=str, default='cmu', help='cmu / mobilenet_thin')
    parser.add_argument('--showBG', type=bool, default=True, help='False to show skeleton only.')
    parser.add_argument('--start_frame', type=int, default=0)
    parser.add_argument('--cog', type=str, default="")
    parser.add_argument('--cog_color', type=str, default='black')
    parser.add_argument('--cog_size', type=str, default='M')
    parser.add_argument('--resize_out_ratio', type=float, default=4.0,
                        help='if provided, resize heatmaps before they are post-processed. default=1.0')
    parser.add_argument('--debug', type=bool, default=False)
    parser.add_argument('--orientation', type=str, default="horizontal")
    parser.add_argument('--plot_image', type=str, default="")
    args = parser.parse_args()
    print(str(args.cog))
    run_video(video=args.video, path=args.path, resize=args.resize, model=args.model, orientation=args.orientation,
                        resize_out_ratio=args.resize_out_ratio, showBG=args.showBG, plot_image=args.plot_image,
                        cog=args.cog, cog_color=args.cog_color, cog_size=args.cog_size, start_frame=args.start_frame, debug=args.debug)

