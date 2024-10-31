import os
os.environ['MUJOCO_GL'] = 'egl'
import pickle
from pathlib import Path
import sys
sys.path.append('../')
from points_class import PointsClass
import yaml
import numpy as np
import cv2
import imageio
import h5py
import pickle as pkl
from tqdm import tqdm

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--preprocessed_data_dir", type=str, required=True, help="path to demo data folder with preprocessed outputs")
    args = parser.parse_args()
    
    save_images = True
    gt_depth = True
    orig_bgr = False
    
    preprocessed_data_dir = args.preprocessed_data_dir

    with open("../cfgs/suite/p3po.yaml") as stream:
        try:
            cfg = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(exc)

    task_name = cfg['task_name']
    coords = pkl.load(open(f'../../coordinates/coords/{task_name}.pkl', 'rb'))
    cfg['num_tracked_points'] = len(coords)
    print(f"Number of tracked points: {cfg['num_tracked_points']}")
    points_class = PointsClass(**cfg)
    dimensions = cfg['dimensions']

    if os.path.exists(f'{task_name}_{dimensions}d_frames_videowise'):
        import shutil
        shutil.rmtree(f'{task_name}_{dimensions}d_frames_videowise')
    os.makedirs(f'{task_name}_{dimensions}d_frames_videowise', exist_ok=True)
    if os.path.exists(f'{task_name}_{dimensions}d_gifs_videowise'):
        import shutil
        shutil.rmtree(f'{task_name}_{dimensions}d_gifs_videowise')
    os.makedirs(f'{task_name}_{dimensions}d_gifs_videowise', exist_ok=True)

    graphs_list = []
    trajectories = {}
    for directory in tqdm(os.listdir(preprocessed_data_dir)):
        if 'demonstration' not in directory:
            continue
        path = f'{preprocessed_data_dir}/{directory}/cam_3_rgb_video.mp4'
        depth_path = f'{preprocessed_data_dir}/{directory}/cam_3_depth.h5'
        print(f"Processing {path}")
        cap = cv2.VideoCapture(path)
        images = []
        depth_images = []
        frame_skip = 1
        counter = 0
        depth_counter = 0
        with h5py.File(depth_path, 'r') as h5_file:
            depth_dataset = h5_file['depth_images']
            while(cap.isOpened()):
                ret, frame = cap.read()
                if not ret:
                    break
                if counter % frame_skip == 0:
                    images.append(frame.copy())
                    if counter < len(depth_dataset):
                        depth_image = depth_dataset[counter]
                        depth_images.append(depth_image)
                        depth_counter = counter
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                counter += 1

        print(f"Read {counter} rgb frames and {depth_counter} depth frames so cutting rgb frames to {depth_counter} frames")
        images = images[:depth_counter]

        graphs = []

        points_class.reset_episode()

        if orig_bgr:
            points_class.add_to_image_list(images[0][:,:,::-1])
        else:
            points_class.add_to_image_list(images[0])

        points_class.find_semantic_similar_points()
        points_class.track_points(is_first_step=True)
        points_class.track_points()

        if gt_depth:
            depth_image = depth_images[0] / 1000
            points_class.set_depth(depth_image)
        else:
            points_class.get_depth()

        graph = points_class.get_points()

        graphs.append(graph)

        if os.path.exists(f'{task_name}_{dimensions}d_frames_videowise/{directory}'):
            import shutil
            shutil.rmtree(f'{task_name}_{dimensions}d_frames_videowise/{directory}')
        os.makedirs(f'{task_name}_{dimensions}d_frames_videowise/{directory}')
        
        if save_images:
            image = points_class.plot_image()[-1]
            cv2.imwrite(f'{task_name}_{dimensions}d_frames_videowise/{directory}/{task_name}_0.png', image)

        for idx, image in enumerate(images[1:]):
            if orig_bgr:
                points_class.add_to_image_list(image[:,:,::-1])
            else:
                points_class.add_to_image_list(image)
            points_class.track_points()
            if gt_depth:
                depth_image = depth_images[idx] / 1000
                points_class.set_depth(depth_image)
            else:
                points_class.get_depth()
            
            graph = points_class.get_points()
                
            graphs.append(graph)
            if save_images:
                image = points_class.plot_image()[-1]
                cv2.imwrite(f'{task_name}_{dimensions}d_frames_videowise/{directory}/{task_name}_{idx+1}.png', image)

        with imageio.get_writer(f'{task_name}_{dimensions}d_gifs_videowise/{directory}_{task_name}.gif', mode='I', duration=0.3) as writer:  
            for filetask_name in os.listdir(f'{task_name}_{dimensions}d_frames_videowise/{directory}'):
                if filetask_name.endswith(".png"):
                    image = imageio.imread(f'{task_name}_{dimensions}d_frames_videowise/{directory}/{filetask_name}')
                    writer.append_data(image)

        trajectories[directory.split('_')[-1]] = graphs

    file_path = f'{preprocessed_data_dir}/{task_name}_{dimensions}d_videowise.pkl'
    with open(str(file_path), 'wb') as f:
        pickle.dump(trajectories, f)
    print(f"Saved points to {file_path}")