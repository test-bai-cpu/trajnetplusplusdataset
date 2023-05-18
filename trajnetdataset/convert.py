"""Create Trajnet data from original datasets."""
import argparse
import shutil
import numpy as np
import random

import pysparkling
import scipy.io

from . import readers
from .scene import Scenes
from .get_type import trajectory_type

import warnings
warnings.filterwarnings("ignore")

def biwi(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .textFile(input_file)
            .map(readers.biwi)
            .cache())


def crowds(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .wholeTextFiles(input_file)
            .values()
            .flatMap(readers.crowds)
            .cache())


def mot(sc, input_file):
    """Was 7 frames per second in original recording."""
    print('processing ' + input_file)
    return (sc
            .textFile(input_file)
            .map(readers.mot)
            .filter(lambda r: r.frame % 2 == 0)
            .cache())


def edinburgh_mydsfile(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .wholeTextFiles(input_file)
            .zipWithIndex()
            .flatMap(readers.edinburgh_mydsfile)
            .cache())


def edinburgh_myedinfile(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .wholeTextFiles(input_file)
            .zipWithIndex()
            .flatMap(readers.edinburgh_myedinfile)
            .cache())


def edinburgh(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .wholeTextFiles(input_file)
            .zipWithIndex()
            .flatMap(readers.edinburgh)
            .cache())


def atc_myfile(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .wholeTextFiles(input_file)
            .zipWithIndex()
            .flatMap(readers.atc_myfile)
            .cache())


def syi(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .wholeTextFiles(input_file)
            .flatMap(readers.syi)
            .cache())


def dukemtmc(sc, input_file):
    print('processing ' + input_file)
    contents = scipy.io.loadmat(input_file)['trainData']
    return (sc
            .parallelize(readers.dukemtmc(contents))
            .cache())


def wildtrack(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .wholeTextFiles(input_file)
            .flatMap(readers.wildtrack)
            .cache())

def cff(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .textFile(input_file)
            .map(readers.cff)
            .filter(lambda r: r is not None)
            .cache())

def lcas(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .textFile(input_file)
            .map(readers.lcas)
            .cache())

def controlled(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .textFile(input_file)
            .map(readers.controlled)
            .cache())

def get_trackrows(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .textFile(input_file)
            .map(readers.get_trackrows)
            .filter(lambda r: r is not None)
            .cache())

def standard(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .textFile(input_file)
            .map(readers.standard)
            .cache())

def car_data(sc, input_file):
    print('processing ' + input_file)
    return (sc
            .wholeTextFiles(input_file)
            .flatMap(readers.car_data)
            .cache())

def write(input_rows, output_file, args):
    """ Write Valid Scenes without categorization """

    print(" Entering Writing ", args.order_frames)
    ## To handle two different time stamps 7:00 and 17:00 of cff
    if args.order_frames:
        frames = sorted(set(input_rows.map(lambda r: r.frame).toLocalIterator()),
                        key=lambda frame: frame % 100000)
    else:
        frames = sorted(set(input_rows.map(lambda r: r.frame).toLocalIterator()))

    # split
    train_split_index = int(len(frames) * args.train_fraction)
    val_split_index = train_split_index + int(len(frames) * args.val_fraction)
    train_frames = set(frames[:train_split_index])
    val_frames = set(frames[train_split_index:val_split_index])
    test_frames = set(frames[val_split_index:])

    # train dataset
    train_rows = input_rows.filter(lambda r: r.frame in train_frames)
    train_output = output_file.format(split='train')
    train_scenes = Scenes(fps=args.fps, start_scene_id=0, args=args).rows_to_file(train_rows, train_output)


## Todo: 把这个start scene id 都设置为零，看看结果有没有改变。理论上test的数据处理是没有任何变化的。确实没有任何变化。。
## 结果是在test里面，对于scene后面的track，每个人比较短，但是在train,val,test_private中，每个人比较长。现在看一下为什么。是因为
## test的只给大家看observe的部分，不给大家看之后的部分。

## 同样，所以在生成test文件夹中的文件的时候，会把train和val中的都清空，因为他们的row都是零

    # validation dataset
    val_rows = input_rows.filter(lambda r: r.frame in val_frames)
    val_output = output_file.format(split='val')
    val_scenes = Scenes(fps=args.fps, start_scene_id=train_scenes.scene_id, args=args).rows_to_file(val_rows, val_output)

    # public test dataset
    test_rows = input_rows.filter(lambda r: r.frame in test_frames)
    test_output = output_file.format(split='test')
    test_scenes = Scenes(fps=args.fps, start_scene_id=val_scenes.scene_id, args=args) # !!! Chunk Stride
    test_scenes.rows_to_file(test_rows, test_output)

    # private test dataset
    private_test_output = output_file.format(split='test_private')
    private_test_scenes = Scenes(fps=args.fps, start_scene_id=val_scenes.scene_id, args=args)
    private_test_scenes.rows_to_file(test_rows, private_test_output)

def categorize(sc, input_file, args):
    """ Categorize the Scenes """

    print(" Entering Categorizing ")
    test_fraction = 1 - args.train_fraction - args.val_fraction

    train_id = 0
    if args.train_fraction:
        print("Categorizing Training Set")
        train_rows = get_trackrows(sc, input_file.replace('split', '').format('train'))
        train_id = trajectory_type(train_rows, input_file.replace('split', '').format('train'),
                                   fps=args.fps, track_id=0, args=args)

    val_id = train_id
    if args.val_fraction:
        print("Categorizing Validation Set")
        val_rows = get_trackrows(sc, input_file.replace('split', '').format('val'))
        val_id = trajectory_type(val_rows, input_file.replace('split', '').format('val'),
                                 fps=args.fps, track_id=train_id, args=args)


    if test_fraction:
        print("Categorizing Test Set")
        test_rows = get_trackrows(sc, input_file.replace('split', '').format('test_private'))
        _ = trajectory_type(test_rows, input_file.replace('split', '').format('test_private'),
                            fps=args.fps, track_id=val_id, args=args)

def edit_goal_file(old_filename, new_filename):
    """ Rename goal files. 
    The name of goal files should be identical to the data files
    """

    shutil.copy("goal_files/train/" + old_filename, "goal_files/train/" + new_filename)
    shutil.copy("goal_files/val/" + old_filename, "goal_files/val/" + new_filename)
    shutil.copy("goal_files/test_private/" + old_filename, "goal_files/test_private/" + new_filename)

def main_edin(train_date_list, val_date_list, test_date_list):
    parser = argparse.ArgumentParser()
    parser.add_argument('--obs_len', type=int, default=8,
                        help='Length of observation')
    parser.add_argument('--pred_len', type=int, default=12,
                        help='Length of prediction')
    parser.add_argument('--train_fraction', default=0.6, type=float,
                        help='Training set fraction')
    parser.add_argument('--val_fraction', default=0.2, type=float,
                        help='Validation set fraction')
    parser.add_argument('--fps', default=2.5, type=float,
                        help='fps')
    parser.add_argument('--order_frames', action='store_true',
                        help='For CFF')
    parser.add_argument('--chunk_stride', type=int, default=10**100,
                        help='Sampling Stride')
    parser.add_argument('--min_length', default=0.0, type=float,
                        help='Min Length of Primary Trajectory')
    parser.add_argument('--synthetic', action='store_true',
                        help='convert synthetic datasets (if false, convert real)')
    parser.add_argument('--all_present', action='store_true',
                        help='filter scenes where all pedestrians present at all times')
    parser.add_argument('--goal_file', default=None,
                        help='Pkl file for goals (required for ORCA sensitive scene filtering)')
    parser.add_argument('--mode', default='default', choices=('default', 'trajnet'),
                        help='mode of ORCA scene generation (required for ORCA sensitive scene filtering)')

    ## For Trajectory categorizing and filtering
    categorizers = parser.add_argument_group('categorizers')
    categorizers.add_argument('--static_threshold', type=float, default=1.0,
                              help='Type I static threshold')
    categorizers.add_argument('--linear_threshold', type=float, default=0.5,
                              help='Type II linear threshold (0.3 for Synthetic)')
    categorizers.add_argument('--inter_dist_thresh', type=float, default=5,
                              help='Type IIId distance threshold for cone')
    categorizers.add_argument('--inter_pos_range', type=float, default=15,
                              help='Type IIId angle threshold for cone (degrees)')
    categorizers.add_argument('--grp_dist_thresh', type=float, default=0.8,
                              help='Type IIIc distance threshold for group')
    categorizers.add_argument('--grp_std_thresh', type=float, default=0.2,
                              help='Type IIIc std deviation for group')
    categorizers.add_argument('--acceptance', nargs='+', type=float, default=[0.1, 1, 1, 1],
                              help='acceptance ratio of different trajectory (I, II, III, IV) types')

    args = parser.parse_args()
    # args.chunk_stride = int(args.pred_len / 4 * 3)
    args.chunk_stride = int(10**10)
    sc = pysparkling.Context()

    # Real datasets conversion (eg. ETH)
    #########################
    ## Training Set
    #########################
    args.train_fraction = 1.0
    args.val_fraction = 0.0

    print("prepare train datasets:")
    for train_date in train_date_list:
        print("---------------------------------")
        print(train_date)
        write(edinburgh_myedinfile(sc, "data/edinburgh-reframe/" + train_date + ".csv"),
            "output_pre/{split}/" + train_date + ".ndjson", args)
        print("-----check1---------")
        categorize(sc, "output_pre/{split}/" + train_date + ".ndjson", args)

#     #########################
#     ## Validation Set
#     #########################
    args.train_fraction = 0.0
    args.val_fraction = 1.0

    print("prepare val datasets:")
    for val_date in val_date_list:
        print("---------------------------------")
        print(val_date)
        write(edinburgh_myedinfile(sc, "data/edinburgh-reframe/" + val_date + ".csv"),
            "output_pre/{split}/" + val_date + ".ndjson", args)
        categorize(sc, "output_pre/{split}/" + val_date + ".ndjson", args)

#     #########################
#     ## Testing Set
#     #########################
    args.train_fraction = 0.0
    args.val_fraction = 0.0
    # here means not use type I data for training and val, but can use them for test.
    args.acceptance = [1.0, 1.0, 1.0, 1.0]
    # args.chunk_stride = 2
    # args.chunk_stride = int(args.pred_len / 4 * 3)
    args.chunk_stride = int(10**100)

    print("prepare test datasets:")
    for test_date in test_date_list:
        print("---------------------------------")
        print(test_date)
        write(edinburgh_myedinfile(sc, "data/edinburgh-reframe/" + test_date + ".csv"),
            "output_pre/{split}/" + test_date + ".ndjson", args)
        categorize(sc, "output_pre/{split}/" + test_date + ".ndjson", args)



def main_atc(train_date_list, val_date_list, test_date_list=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--obs_len', type=int, default=8,
                        help='Length of observation')
    parser.add_argument('--pred_len', type=int, default=12,
                        help='Length of prediction')
    parser.add_argument('--train_fraction', default=0.6, type=float,
                        help='Training set fraction')
    parser.add_argument('--val_fraction', default=0.2, type=float,
                        help='Validation set fraction')
    parser.add_argument('--fps', default=2.5, type=float,
                        help='fps')
    parser.add_argument('--order_frames', action='store_true',
                        help='For CFF')
    parser.add_argument('--chunk_stride', type=int, default=1000000,
                        help='Sampling Stride')
    parser.add_argument('--min_length', default=0.0, type=float,
                        help='Min Length of Primary Trajectory')
    parser.add_argument('--synthetic', action='store_true',
                        help='convert synthetic datasets (if false, convert real)')
    parser.add_argument('--all_present', action='store_true',
                        help='filter scenes where all pedestrians present at all times')
    parser.add_argument('--goal_file', default=None,
                        help='Pkl file for goals (required for ORCA sensitive scene filtering)')
    parser.add_argument('--mode', default='default', choices=('default', 'trajnet'),
                        help='mode of ORCA scene generation (required for ORCA sensitive scene filtering)')
    parser.add_argument('--train_atc_file', type=str, help='atc file for training phase')

    ## For Trajectory categorizing and filtering
    categorizers = parser.add_argument_group('categorizers')
    categorizers.add_argument('--static_threshold', type=float, default=1.0,
                              help='Type I static threshold')
    categorizers.add_argument('--linear_threshold', type=float, default=0.5,
                              help='Type II linear threshold (0.3 for Synthetic)')
    categorizers.add_argument('--inter_dist_thresh', type=float, default=5,
                              help='Type IIId distance threshold for cone')
    categorizers.add_argument('--inter_pos_range', type=float, default=15,
                              help='Type IIId angle threshold for cone (degrees)')
    categorizers.add_argument('--grp_dist_thresh', type=float, default=0.8,
                              help='Type IIIc distance threshold for group')
    categorizers.add_argument('--grp_std_thresh', type=float, default=0.2,
                              help='Type IIIc std deviation for group')
    categorizers.add_argument('--acceptance', nargs='+', type=float, default=[0.1, 1, 1, 1],
                              help='acceptance ratio of different trajectory (I, II, III, IV) types')

    args = parser.parse_args()
    # args.chunk_stride = int(args.pred_len / 4 * 3)
    # args.chunk_stride = int(10**100)
    args.chunk_stride = int(args.pred_len / 4 * 3)
    sc = pysparkling.Context()

    #########################
    ## Training Set
    #########################
    args.train_fraction = 1.0
    args.val_fraction = 0.0

    print("prepare train datasets:")
    for train_date in train_date_list:
        print("---------------------------------")
        print(train_date)
        write(atc_myfile(sc, "data/atc-train-1024-long/train/" + train_date + ".csv"),
            "output_pre/{split}/" + train_date + ".ndjson", args)
        categorize(sc, "output_pre/{split}/" + train_date + ".ndjson", args)

#     #########################
#     ## Validation Set
#     #########################
    args.train_fraction = 0.0
    args.val_fraction = 1.0

    print("prepare val datasets:") 
    for val_date in val_date_list:
        print("---------------------------------")
        print(val_date)
        write(atc_myfile(sc, "data/atc-train-1024-long/val/" + val_date + ".csv"),
            "output_pre/{split}/" + val_date + ".ndjson", args)
        categorize(sc, "output_pre/{split}/" + val_date + ".ndjson", args)

    #########################
    ## Testing Set
    #########################
    # args.train_fraction = 0.0
    # args.val_fraction = 0.0
    # # here means not use type I data for training and val, but can use them for test.
    # args.acceptance = [1.0, 1.0, 1.0, 1.0]
    # # args.chunk_stride = 2
    # # args.chunk_stride = int(args.pred_len / 4 * 3)
    # args.chunk_stride = int(10**100)

    # print("prepare test datasets:")
    # for test_date in test_date_list:
    #     print("---------------------------------")
    #     print(test_date)
    #     write(atc_myfile(sc, "data/1024/" + test_date + ".csv"),
    #         "output_pre/{split}/" + test_date + ".ndjson", args)
    #     categorize(sc, "output_pre/{split}/" + test_date + ".ndjson", args)

def main_atc_long_traj_train():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obs_len', type=int, default=8,
                        help='Length of observation')
    parser.add_argument('--pred_len', type=int, default=12,
                        help='Length of prediction')
    parser.add_argument('--train_fraction', default=0.6, type=float,
                        help='Training set fraction')
    parser.add_argument('--val_fraction', default=0.2, type=float,
                        help='Validation set fraction')
    parser.add_argument('--fps', default=2.5, type=float,
                        help='fps')
    parser.add_argument('--order_frames', action='store_true',
                        help='For CFF')
    parser.add_argument('--chunk_stride', type=int, default=2,
                        help='Sampling Stride')
    parser.add_argument('--min_length', default=0.0, type=float,
                        help='Min Length of Primary Trajectory')
    parser.add_argument('--synthetic', action='store_true',
                        help='convert synthetic datasets (if false, convert real)')
    parser.add_argument('--direct', action='store_true',
                        help='directy convert synthetic datasets using commandline')
    parser.add_argument('--all_present', action='store_true',
                        help='filter scenes where all pedestrians present at all times')
    parser.add_argument('--orca_file', default=None,
                        help='Txt file for ORCA trajectories, required in direct mode')
    parser.add_argument('--goal_file', default=None,
                        help='Pkl file for goals (required for ORCA sensitive scene filtering)')
    parser.add_argument('--output_filename', default=None,
                        help='name of the output dataset filename constructed in .ndjson format, required in direct mode')
    parser.add_argument('--mode', default='default', choices=('default', 'trajnet'),
                        help='mode of ORCA scene generation (required for ORCA sensitive scene filtering)')
    parser.add_argument('--train_atc_file', default=None, type=str, help='atc file for training phase')
    parser.add_argument('--batch_str', default=None, type=str, help='batch number for multi random sets')

    ## For Trajectory categorizing and filtering
    categorizers = parser.add_argument_group('categorizers')
    categorizers.add_argument('--static_threshold', type=float, default=1.0,
                              help='Type I static threshold')
    categorizers.add_argument('--linear_threshold', type=float, default=0.5,
                              help='Type II linear threshold (0.3 for Synthetic)')
    categorizers.add_argument('--inter_dist_thresh', type=float, default=5,
                              help='Type IIId distance threshold for cone')
    categorizers.add_argument('--inter_pos_range', type=float, default=15,
                              help='Type IIId angle threshold for cone (degrees)')
    categorizers.add_argument('--grp_dist_thresh', type=float, default=0.8,
                              help='Type IIIc distance threshold for group')
    categorizers.add_argument('--grp_std_thresh', type=float, default=0.2,
                              help='Type IIIc std deviation for group')
    categorizers.add_argument('--acceptance', nargs='+', type=float, default=[0.1, 1, 1, 1],
                              help='acceptance ratio of different trajectory (I, II, III, IV) types')

    args = parser.parse_args()
    # args.chunk_stride = int(args.pred_len / 4 * 3)
    # args.chunk_stride = int(10**100)
    args.chunk_stride = int(args.pred_len / 4 * 3)
    sc = pysparkling.Context()

    #########################
    ## Training Set
    #########################
    args.train_fraction = 1.0
    args.val_fraction = 0.0

    print("prepare train datasets:")
    print("---------------------------------")

    # file_name = "data/atc-long-traj-train-frame/" + args.batch_str + "/train/" + args.train_atc_file + ".csv"
    file_name = "data/atc-train-1024-long/train/" + args.train_atc_file + ".csv"
    write(atc_myfile(sc, file_name),
        "output_pre/{split}/" + args.train_atc_file + ".ndjson", args)
    categorize(sc, "output_pre/{split}/" + args.train_atc_file + ".ndjson", args)

# #     #########################
# #     ## Validation Set
# #     #########################
    args.train_fraction = 0.0
    args.val_fraction = 1.0

    print("prepare val datasets:") 
    print("---------------------------------")
    
    # file_name = "data/atc-long-traj-train-frame/" + args.batch_str + "/val/" + args.train_atc_file + ".csv"
    file_name = "data/atc-train-1024-long/val/" + args.train_atc_file + ".csv"
    write(atc_myfile(sc, file_name),
        "output_pre/{split}/" + args.train_atc_file + ".ndjson", args)
    categorize(sc, "output_pre/{split}/" + args.train_atc_file + ".ndjson", args)
    #########################
    ## Testing Set
    #########################
    # args.train_fraction = 0.0
    # args.val_fraction = 0.0
    # # here means not use type I data for training and val, but can use them for test.
    # args.acceptance = [1.0, 1.0, 1.0, 1.0]
    # # args.chunk_stride = 2
    # # args.chunk_stride = int(args.pred_len / 4 * 3)
    # args.chunk_stride = int(10**100)

    # print("prepare test datasets:")
    # for test_date in ["1028", "1031", "1104"]:
    # # for test_date in ["1028"]:
    #     print("---------------------------------")
    #     print(test_date)
    #     # for split_num in range(1, 11):
    #     # for split_num in range(1):
    #     #     write(atc_myfile(sc, "data/atc-long-traj-train-frame/test-split/" + test_date + "-" + str(split_num) + ".csv"),
    #     #         "output_pre/{split}/" + test_date + "-" + str(split_num) + ".ndjson", args)
    #     #     categorize(sc, "output_pre/{split}/" + test_date + "-" + str(split_num) + ".ndjson", args)
        
    #     write(atc_myfile(sc, "data/atc-test/" + test_date + "-60.csv"),
    #         "output_pre/{split}/" + test_date + ".ndjson", args)
    #     categorize(sc, "output_pre/{split}/" + test_date + ".ndjson", args)
        

if __name__ == '__main__':
    
    ############################# EDIN #############################
    # all_dates = ["0106", "0107", "0111", "0113", "0114", "0115", "0118", "0119",
    #             "0603", "0604", "0614", "0616", "0618", "0624", "0625", "0629", "0630", 
    #             "0701", "0712", "0719", "0722", "0726", "0730",
    #             "0826", "0827", "0828",
    #             "0901", "0902", "0904", "0910", "0911", "0916", "0918", "0922", "0923", "0928", "0929", "0930",
    #             "1002", "1006", "1007", "1008", "1009",
    #             "1215", "1216"]
    # train_date_list = ["0106", "0107", "0111"]
    # val_date_list = ["0113", "0114"]
    
    
    # # train_date_list = ["0106"]
    # # val_date_list = ["0113"]
    # # test_date_list = ["0115"]
    # test_date_list = ["0115", "0118", "0119",
    #                 "0603", "0604", "0614", "0616", "0618", "0624", "0625", "0629", "0630", 
    #                 "0701", "0712", "0719", "0722", "0726", "0730",
    #                 "0826", "0827", "0828",
    #                 "0901", "0902", "0904", "0910", "0911", "0916", "0918", "0922", "0923", "0928", "0929", "0930",
    #                 "1002", "1006", "1007", "1008", "1009",
    #                 "1215", "1216"]
    # # test_date_list = ["0115"]

    # main_edin(train_date_list, val_date_list, test_date_list)
    #################################################################



    ############################# ATC #############################
    all_dates = ["1024", "1028", "1031", "1104"]
    # train_date_list = ["1024-train"]
    # val_date_list = ["1024-val"]
    # test_date_list = ["1028", "1031", "1104"]
    
    train_date_list = ["1024-" + str(bn) for bn in range(1,11)]
    val_date_list = ["1024-" + str(bn) for bn in range(1,11)]
    # test_date_list = ["1024-3"]

    main_atc(train_date_list, val_date_list)
    #################################################################
    
    ############################# ATC workshop: long traj train #####
    # main_atc_long_traj_train()
    #################################################################