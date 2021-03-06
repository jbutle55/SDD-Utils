import os
import subprocess
import numpy as np
import random
import pickle
import cv2
import math
import xml.etree.cElementTree as ET
import json


def assert_path(path, error_message):
    assert os.path.exists(path), error_message


def count_files(path, filename_starts_with=''):
    files = [f for f in os.listdir(path)if os.path.isfile(os.path.join(path, f))
                     and f.startswith(filename_starts_with)]
    return len(files)


def touch(fname, times=None):
    with open(fname, 'a'):
        os.utime(fname, times)


def init_directories():
    # Setup the directory structure.
    if not os.path.exists(destination_path):
        os.makedirs(os.path.join(destination_path, 'images'))
        os.makedirs(os.path.join(destination_path, 'ImageSets', 'Main'))
        os.makedirs(os.path.join(destination_path, 'Annotations'))
        os.makedirs(os.path.join(destination_path, 'Annotations_json'))
        os.makedirs(os.path.join(destination_path, 'pickle_store'))
        os.makedirs(os.path.join(destination_path, 'labels'))

    # Flush the train-val-test split. A new split will be created each time this script is run.
    for f in os.listdir(os.path.join(destination_path, 'ImageSets', 'Main')):
        os.remove(os.path.join(destination_path, 'ImageSets', 'Main', f))

    # Creating empty files.
    touch(os.path.join(destination_path, 'ImageSets', 'Main', 'train.txt'))
    touch(os.path.join(destination_path, 'ImageSets', 'Main', 'val.txt'))
    touch(os.path.join(destination_path, 'ImageSets', 'Main', 'test.txt'))
    touch(os.path.join(destination_path, 'ImageSets', 'Main', 'trainval.txt'))


def split_video(video_file, image_name_prefix):
    return subprocess.check_output('ffmpeg -i ' + os.path.abspath(video_file) + ' '+ image_name_prefix +'%d.jpg', shell=True, cwd=os.path.join(destination_path, 'images'))


def log(message, level='info'):
    formatters = {
        'GREEN': '\033[92m',
        'END': '\033[0m',
    }
    print(message)


def write_to_file(filename, content):
    f = open(filename, 'a')
    f.write(content+'\n')


def split_dataset(number_of_frames, split_ratio, file_name_prefix):
    assert sum(split_ratio) <= 1, 'Split ratio cannot be more than 1.'

    train, val, test = np.array(split_ratio) * number_of_frames

    test_images = random.sample(range(1, number_of_frames+1), int(test))
    val_images = random.sample(tuple(set(range(1, number_of_frames+1)) - set(test_images)), int(val))
    train_images = random.sample(tuple(set(range(1, number_of_frames+1)) - set(test_images) - set(val_images)), int(train))

    for index in train_images:
        write_to_file(os.path.join(destination_path, 'ImageSets', 'Main', 'train.txt'), file_name_prefix+str(index))
        write_to_file(os.path.join(destination_path, 'ImageSets', 'Main', 'trainval.txt'), file_name_prefix+str(index))

    for index in val_images:
        write_to_file(os.path.join(destination_path, 'ImageSets', 'Main', 'val.txt'), file_name_prefix+str(index))
        write_to_file(os.path.join(destination_path, 'ImageSets', 'Main', 'trainval.txt'), file_name_prefix+str(index))

    for index in test_images:
        write_to_file(os.path.join(destination_path, 'ImageSets', 'Main', 'test.txt'), file_name_prefix+str(index))


def annotate_frames(sdd_annotation_file, dest_path, filename_prefix, number_of_frames):

    # Pickle the actual SDD annotation
    pickle_file = os.path.join(destination_path, 'pickle_store', filename_prefix + 'annotation.pkl')
    if os.path.exists(pickle_file):
        with open(pickle_file, 'rb') as fid:
            sdd_annotation = pickle.load(fid)
    else:
        sdd_annotation = np.genfromtxt(sdd_annotation_file, delimiter=' ', dtype=np.str)
        with open(pickle_file, 'wb') as fid:
            pickle.dump(sdd_annotation, fid)

    # Create VOC style annotation.
    first_image_path = os.path.join(destination_path, 'images', filename_prefix+'1.jpg')
    assert_path(first_image_path, 'Cannot find the images. Trying to access: ' + first_image_path)
    first_image = cv2.imread(first_image_path)
    height, width, depth = first_image.shape

    for frame_number in range(1, number_of_frames+1):
        annotation = ET.Element("annotation")
        ET.SubElement(annotation, "folder").text = destination_folder_name
        source = ET.SubElement(annotation, "source")
        ET.SubElement(source, "database").text = 'Stanford Drone Dataset'
        size = ET.SubElement(annotation, "size")
        ET.SubElement(size, "width").text = str(width)
        ET.SubElement(size, "height").text = str(height)
        ET.SubElement(size, "depth").text = str(depth)
        ET.SubElement(annotation, "segmented").text = '0'
        ET.SubElement(annotation, "filename").text = filename_prefix + str(frame_number)

        annotations_in_frame = sdd_annotation[sdd_annotation[:, 5] == str(frame_number)]

        for annotation_data in annotations_in_frame:
            object = ET.SubElement(annotation, "object")
            ET.SubElement(object, "name").text = annotation_data[9].replace('"','')
            ET.SubElement(object, "pose").text = 'Unspecified'
            ET.SubElement(object, "truncated").text = annotation_data[7] # occluded
            ET.SubElement(object, "difficult").text = '0'
            bndbox = ET.SubElement(object, "bndbox")
            ET.SubElement(bndbox, "xmin").text = annotation_data[1]
            ET.SubElement(bndbox, "ymin").text = annotation_data[2]
            ET.SubElement(bndbox, "xmax").text = annotation_data[3]
            ET.SubElement(bndbox, "ymax").text = annotation_data[4]

        xml_annotation = ET.ElementTree(annotation)
        xml_annotation.write(os.path.join(dest_path, filename_prefix + str(frame_number) + ".xml"))


def annotate_frames_json(sdd_annotation_file, dest_path, filename_prefix, number_of_frames):

    jpeg_ids = {'Pedestrian': 0,
                'Biker': 1,
                'Cart': 2,
                'Skater': 3,
                'Bus': 4,
                'Car': 5}

    # Pickle the actual SDD annotation
    pickle_file = os.path.join(destination_path, 'pickle_store', filename_prefix + 'annotation.pkl')
    if os.path.exists(pickle_file):
        with open(pickle_file, 'rb') as fid:
            sdd_annotation = pickle.load(fid)
    else:
        sdd_annotation = np.genfromtxt(sdd_annotation_file, delimiter=' ', dtype=np.str)
        with open(pickle_file, 'wb') as fid:
            pickle.dump(sdd_annotation, fid)

    # Create COCO style annotation.
    first_image_path = os.path.join(destination_path, 'images', filename_prefix+'1.jpg')
    assert_path(first_image_path, 'Cannot find the images. Trying to access: ' + first_image_path)
    first_image = cv2.imread(first_image_path)
    height, width, depth = first_image.shape

    coco = dict()
    coco['info'] = []
    coco['info'].append({'description': 'Standford UAV Dataset'})
    coco['images'] = []
    coco['annotations'] = []

    coco['categories'] = [{'id': 0, 'name': 'Pedestrian'},
                          {'id': 1, 'name': 'Biker'},
                          {'id': 2, 'name': 'Cart'},
                          {'id': 3, 'name': 'Skater'},
                          {'id': 4, 'name': 'Bus'},
                          {'id': 5, 'name': 'Car'}]

    prev_max_id = 0  # To ensure unique annotation IDs

    for frame_number in range(1, number_of_frames + 1):
        img = dict()
        # Image info
        img['id'] = frame_number
        img['width'] = width
        img['height'] = height
        img['depth'] = depth
        img['file_name'] = filename_prefix + str(frame_number) + '.jpg'

        coco['images'].append(img)

        annotations_in_frame = sdd_annotation[sdd_annotation[:, 5] == str(frame_number)]

        for count, annotation_data in enumerate(annotations_in_frame, prev_max_id):
            annots = dict()
            category = annotation_data[9].replace('"', '')

            annots['id'] = int(frame_number) + count  # ID of unique object
            annots['image_id'] = frame_number
            annots['category_id'] = int(jpeg_ids[category])  # Category class

            box_width = abs(float(annotation_data[3]) - float(annotation_data[1]))
            box_height = abs(float(annotation_data[4]) - float(annotation_data[2]))
            annots['bbox'] = [float(annotation_data[1]), float(annotation_data[2]), box_width, box_height]
            #annots['iscrowd'] = annotation_data[7]
            annots['iscrowd'] = 0
            annots['bbox_mode'] = 1
            annots['area'] = box_width * box_height

            coco['annotations'].append(annots)

            prev_max_id = count

        # Create tiny test dataset
        if frame_number == 10:
            with open(os.path.join(dest_path, filename_prefix + 'tiny' + '.json'), 'w') as jfile:
                json.dump(coco, jfile, indent=4)
                jfile.close()
    with open(os.path.join(dest_path, filename_prefix + '.json'), 'w') as jfile:
        json.dump(coco, jfile, indent=4)
        jfile.close()


def annotate_frames_txt(sdd_annotation_file, dest_path, filename_prefix, number_of_frames):

    jpeg_ids = {'Pedestrian': 0,
                'Biker': 1,
                'Cart': 2,
                'Skater': 3,
                'Bus': 4,
                'Car': 5}

    # Pickle the actual SDD annotation
    pickle_file = os.path.join(destination_path, 'pickle_store', filename_prefix + 'annotation.pkl')
    if os.path.exists(pickle_file):
        with open(pickle_file, 'rb') as fid:
            sdd_annotation = pickle.load(fid)
    else:
        sdd_annotation = np.genfromtxt(sdd_annotation_file, delimiter=' ', dtype=np.str)
        with open(pickle_file, 'wb') as fid:
            pickle.dump(sdd_annotation, fid)

    # Create COCO style annotation.
    first_image_path = os.path.join(destination_path, 'images', filename_prefix+'1.jpg')
    assert_path(first_image_path, 'Cannot find the images. Trying to access: ' + first_image_path)
    first_image = cv2.imread(first_image_path)
    height, width, depth = first_image.shape

    for frame_number in range(1, number_of_frames + 1):
        annotations_in_frame = sdd_annotation[sdd_annotation[:, 5] == str(frame_number)]
        filename = filename_prefix + str(frame_number) + '.txt'

        with open(os.path.join(dest_path, filename), 'w') as fout:
            for annotation_data in annotations_in_frame:
                category = annotation_data[9].replace('"', '')

                if int(annotation_data[1]) < 0:
                    annotation_data[1] = '0'
                if int(annotation_data[3]) > width:
                    annotation_data[3] = str(width)
                if int(annotation_data[2]) < 0:
                    annotation_data[2] = '0'
                if int(annotation_data[4]) > height:
                    annotation_data[4] = str(height)

                box_width = abs(int(annotation_data[3]) - int(annotation_data[1]))
                box_height = abs(int(annotation_data[4]) - int(annotation_data[2]))

                x_center = int(annotation_data[1]) + (box_width / 2)
                y_center = int(annotation_data[2]) + (box_height / 2)

                box_width = box_width / width  # Normalize
                box_height = box_height / height  # Normalize

                x_center = x_center / width  # Normalize
                y_center = y_center / height  # Normalize

                fout.write('{} {} {} {} {}\n'.format(jpeg_ids[category], x_center, y_center, box_width, box_height))
            fout.close()

    return


def calculate_share(num_training_images, num_val_images, num_testing_images):
    # Returns how many frame should be each videos in train/val/test sets.
    train_videos = 0
    val_videos = 0
    test_videos = 0
    for scene in videos_to_be_processed:
        path = os.path.join(dataset_path, 'videos', scene)
        assert_path(path, path + ' not found.')

        videos = videos_to_be_processed.get(scene)
        if len(videos) > 0:
            for video_index in videos.keys():
                split_ratio = videos.get(video_index)
                if split_ratio[0] == 1:
                    train_videos += 1
                elif split_ratio[1] == 1:
                    val_videos += 1
                elif split_ratio[2] == 1:
                    test_videos += 1

    return (num_training_images/train_videos, num_val_images/val_videos, num_testing_images/test_videos)


def split_dataset_uniformly(number_of_frames, split_ratio, share, file_name_prefix):
    index_of_one = split_ratio.index(1)
    share_of_this_video = share[index_of_one]
    skip_by = int(math.ceil(float(number_of_frames)/share_of_this_video))
    image_index = [i for i in range(1, number_of_frames+1, skip_by)]

    for index in image_index:
        if index_of_one == 0:
            # Training
            write_to_file(os.path.join(destination_path, 'ImageSets', 'Main', 'train.txt'),
                          file_name_prefix + str(index))
            write_to_file(os.path.join(destination_path, 'ImageSets', 'Main', 'trainval.txt'),
                          file_name_prefix + str(index))
        elif index_of_one == 1:
            # Validation
            write_to_file(os.path.join(destination_path, 'ImageSets', 'Main', 'val.txt'), file_name_prefix + str(index))
            write_to_file(os.path.join(destination_path, 'ImageSets', 'Main', 'trainval.txt'),
                          file_name_prefix + str(index))
        elif index_of_one == 2:
            # Testing
            write_to_file(os.path.join(destination_path, 'ImageSets', 'Main', 'test.txt'), file_name_prefix + str(index))


def split_and_annotate(num_training_images=None, num_val_images=None, num_testing_images=None,
                       json_annot=False, txt_annot=False):
    assert_path(dataset_path, ''.join(e for e in dataset_path if e.isalnum()) + ' folder should be found in the cwd of this script.')
    init_directories()
    if num_training_images is not None and num_val_images is not None and num_testing_images is not None:
        share = calculate_share(num_training_images, num_val_images, num_testing_images)
    for scene in videos_to_be_processed:
        path = os.path.join(dataset_path, 'videos', scene)
        assert_path(path, path + ' not found.')

        videos = videos_to_be_processed.get(scene)
        if len(videos) > 0:
            for video_index in videos.keys():
                video_path = os.path.join(path, 'video' + str(video_index))
                assert_path(video_path, video_path + ' not found.')
                assert count_files(video_path) == 1, video_path+' should contain one file.'

                # Split video into frames
                # Check whether the video has already been made into frames
                jpeg_image_path = os.path.join(destination_path, 'images')
                image_name_prefix = scene + '_video' + str(video_index) + '_'
                video_file = os.path.join(video_path, 'video.mov')
                if count_files(jpeg_image_path, image_name_prefix) == 0:
                    # Split Video
                    log('Splitting ' + video_file)
                    split_video(video_file, image_name_prefix)
                    log('Splitting ' + video_file + ' complete.')

                    # Annotate
                    log('Annotating frames from ' + video_file)
                    sdd_annotation_file = os.path.join(dataset_path, 'annotations', scene,
                                                       'video' + str(video_index), 'annotations.txt')
                    assert_path(sdd_annotation_file, 'Annotation file not found. '
                                                     'Trying to access ' + sdd_annotation_file)
                    dest_path = os.path.join(destination_path, 'Annotations')
                    number_of_frames = count_files(jpeg_image_path, image_name_prefix)
                    # Create xml, json and txt annotations
                    annotate_frames(sdd_annotation_file, dest_path, image_name_prefix, number_of_frames)
                    dest_path_json = os.path.join(destination_path, 'Annotations_json')
                    annotate_frames_json(sdd_annotation_file, dest_path_json, image_name_prefix, number_of_frames)
                    dest_path = os.path.join(destination_path, 'labels')
                    annotate_frames_txt(sdd_annotation_file, dest_path, image_name_prefix, number_of_frames)

                    log('Annotation Complete.')

                else:
                    log(video_file + ' is already split into frames. Skipping...')

                # Create train-val-test split
                number_of_frames = count_files(jpeg_image_path, image_name_prefix)
                split_ratio = videos.get(video_index)
                if num_training_images is not None and num_val_images is not None and num_testing_images is not None:
                    split_dataset_uniformly(number_of_frames, split_ratio, share, image_name_prefix)
                else:
                    split_dataset(number_of_frames, split_ratio, image_name_prefix)
                log('Successfully created train-val-test split.')
    log('Done.')


if __name__ == '__main__':

    # --------------------------------------------------------
    # videos_to_be_processed is a dictionary.
    # Keys in this dictionary should match the 'scenes' in Stanford Drone Dataset.
    # Value for each key is also a dictionary.
    #   - The number of items in the dictionary, can atmost be the number of videos each 'scene'
    #   - Each item in the dictionary is of the form {video_number:fraction_of_images_to_be_split_into_train_val_test_set}
    #   - eg: {2:(.7, .2, .1)} means 0.7 fraction of the images from Video2, should be put into training set,
    #                                0.2 fraction to validation set and
    #                                0.1 fraction to test set.
    #                                Also, training and validation images are merged into trainVal set.
    # --------------------------------------------------------

    # videos_to_be_processed = {'bookstore': {0: (.5, .2, .3)},
    #                           'coupa': {0: (.5, .2, .3)},
    #                           'deathCircle': {0: (.5, .2, .3)},
    #                           'gates': {0: (.5, .2, .3)},
    #                           'hyang': {0: (.5, .2, .3)},
    #                           'little': {0: (.5, .2, .3)},
    #                           'nexus': {0: (.5, .2, .3)},
    #                           'quad': {0: (.5, .2, .3)}}

    # Uniform Sub Sampling : Split should contain only 0 / 1
    # videos_to_be_processed = {'bookstore': {1: (1, 0, 0), 2: (0, 1, 0), 3: (0, 0, 1)},
    #                           'coupa': {0: (1, 0, 0), 2: (0, 1, 0), 3: (0, 0, 1)},
    #                           'deathCircle': {0: (1, 0, 0), 2: (0, 1, 0), 3: (0, 0, 1)},
    #                           'gates': {0: (1, 0, 0), 2: (0, 1, 0), 3: (0, 0, 1)},
    #                           'hyang': {0: (1, 0, 0), 2: (0, 1, 0), 3: (0, 0, 1)},
    #                           'little': {0: (1, 0, 0), 2: (0, 1, 0), 3: (0, 0, 1)},
    #                           'nexus': {0: (1, 0, 0), 2: (0, 1, 0), 3: (0, 0, 1)},
    #                           'quad': {0: (1, 0, 0), 2: (0, 1, 0), 3: (0, 0, 1)}}

    videos_to_be_processed = {'nexus': {0: (1, 0, 0), 1: (1, 0, 0), 2: (1, 0, 0),
                                        3: (1, 0, 0), 4: (1, 0, 0), 5: (1, 0, 0),
                                        6: (1, 0, 0), 7: (1, 0, 0), 8: (1, 0, 0),
                                        9: (0, 0, 1), 10: (0, 0, 1), 11: (0, 0, 1)},
                              'deathCircle': {0: (0, 1, 0), 1: (0, 1, 0), 2: (0, 1, 0),
                                              3: (0, 1, 0), 4: (0, 1, 0)}}

    #videos_to_be_processed = {'nexus': {0: (1, 0, 0), 1: (0, 1, 0), 2: (0, 0, 1)}}

    num_training_images = 40000
    num_val_images = 10000
    num_testing_images = 2000

    dataset_path = '/home/justin/Data/Stanford'
    #dataset_path = '/Users/justinbutler/Desktop/StanfordDataset'
    destination_folder_name = 'sdd'
    destination_path = os.path.join(dataset_path, destination_folder_name)

    # split_and_annotate()
    split_and_annotate(num_training_images, num_val_images, num_testing_images)
