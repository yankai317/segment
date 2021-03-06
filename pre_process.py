"""

获取固定取样方式下的训练数据
首先将灰度值超过upper和低于lower的灰度进行截断
然后调整slice thickness，然后将slice的分辨率调整为256*256
只有包含肝脏以及肝脏上下 expand_slice 张slice作为训练样本
最后将输入数据分块，以轴向 stride 张slice为步长进行取样

网络输入为256*256*size
当前脚本依然对金标准进行了缩小，如果要改变，直接修改第70行就行
"""

import os
import shutil
from time import time
import re
import numpy as np
import SimpleITK as sitk
import scipy.ndimage as ndimage

upper = 500
lower = -100

stride = 3  # 取样的步长
down_scale = 1
slice_thickness = 1


# root = '/mnt/data/dataset/liver/'


def read_dicom(path):
    print(path)
    if os.path.isdir(path):
        reader = sitk.ImageSeriesReader()
        dicoms = reader.GetGDCMSeriesFileNames(path)
        reader.SetFileNames(dicoms)
        image = reader.Execute()
        return image
    else:
        image = sitk.ReadImage(path)
        return image

def set_Window(image, max, min):            #统一设置灰度值范围
    array = sitk.GetArrayFromImage(image)
    array_max = np.max(array)
    array_min = np.min(array)
    image_out = sitk.IntensityWindowing(image, array_min * 1.0, array_max * 1.0, min, max)
    return image_out

# 用来记录产生的数据的序号


def process_3d():
    root = '/workspace/mnt/group/alg-pro/yankai/segment/data/liver/'

    new_ct_dir = '/workspace/mnt/group/alg-pro/yankai/segment/data/pre_process'
    new_seg_dir = '/workspace/mnt/group/alg-pro/yankai/segment/data/pre_process'
    file_list = [file for file in os.listdir(root)]
    for ct_file in file_list:
        ct_dir = os.path.join(root + ct_file, 'PATIENT_DICOM')
        seg_dir = os.path.join(os.path.join(root + ct_file, 'MASKS_DICOM'), 'liver')
        masks = os.listdir(os.path.join(root + ct_file, 'MASKS_DICOM'))

        tumors = [mask for mask in masks if 'livertumor' in mask]
        seg = read_dicom(seg_dir)
        seg_array = sitk.GetArrayFromImage(seg)
        seg_array[seg_array == 255] = 1

        for tumor in tumors:
            tumor_seg = read_dicom(os.path.join(os.path.join(root + ct_file, 'MASKS_DICOM'), tumor))
            tumor_array = sitk.GetArrayFromImage(tumor_seg)
            seg_array[tumor_array == 255] = 2

        file_index = 0

        # 用来统计最终剩下的slice数量
        left_slice_list = []

        start_time = time()
        print("process:", ct_file)
        # 将CT和金标准入读内存
        # ct = sitk.ReadImage(os.path.join(ct_dir, ct_file), sitk.sitkInt16)
        ct = read_dicom(ct_dir)
        ct_array = sitk.GetArrayFromImage(ct)

        # seg = sitk.ReadImage(os.path.join(seg_dir, ct_file.replace('volume', 'segmentation')), sitk.sitkInt8)

        # 将金标准中肝脏和肝肿瘤的标签融合为一个
        # seg_array[seg_array > 0] = 1

        # 将灰度值在阈值之外的截断掉
        ct_array[ct_array > upper] = upper
        ct_array[ct_array < lower] = lower

        # 对CT和金标准进行插值，插值之后的array依然是int类型
        print("process chazhi")

        ct_array = ndimage.zoom(ct_array, (ct.GetSpacing()[-1] / slice_thickness, down_scale, down_scale), order=3)
        seg_array = ndimage.zoom(seg_array, (ct.GetSpacing()[-1] / slice_thickness, down_scale, down_scale), order=0)

        # 找到肝脏区域开始和结束的slice，并各向外扩张
        # z = np.any(seg_array, axis=(1, 2))
        # start_slice, end_slice = np.where(z)[0][[0, -1]]
        #
        # # 两个方向上各扩张个slice
        # if start_slice - expand_slice < 0:
        #     start_slice = 0
        # else:
        #     start_slice -= expand_slice
        #
        # if end_slice + expand_slice >= seg_array.shape[0]:
        #     end_slice = seg_array.shape[0] - 1
        # else:
        #     end_slice += expand_slice
        #
        # # 如果这时候剩下的slice数量不足size，直接放弃，这样的数据很少
        # if end_slice - start_slice + 1 < size:
        #     print('!!!!!!!!!!!!!!!!')
        #     print(ct_file, 'too little slice')
        #     print('!!!!!!!!!!!!!!!!')
        #     continue
        #
        # new_ct_array = ct_array[start_slice:end_slice + 1, :, :]
        # new_seg_array = seg_array[start_slice:end_slice + 1, :, :]

        new_ct = sitk.GetImageFromArray(ct_array)

        new_ct.SetDirection(ct.GetDirection())
        new_ct.SetOrigin(ct.GetOrigin())
        new_ct.SetSpacing(
            (ct.GetSpacing()[0] * int(1 / down_scale), ct.GetSpacing()[1] * int(1 / down_scale), slice_thickness))

        new_seg = sitk.GetImageFromArray(seg_array)
        new_seg.SetDirection(ct.GetDirection())
        new_seg.SetOrigin(ct.GetOrigin())
        new_seg.SetSpacing(
            (ct.GetSpacing()[0] * int(1 / down_scale), ct.GetSpacing()[1] * int(1 / down_scale), slice_thickness))

        new_ct_name = 'volume-' + str(int(ct_file.split('.')[-1]) + 150) + '.nii'
        new_seg_name = 'segmentation-' + str(int(ct_file.split('.')[-1]) + 150) + '.nii'

        print("write ", new_ct_name)
        print("write ", new_seg_name)
        sitk.WriteImage(new_ct, os.path.join(new_ct_dir, new_ct_name))
        sitk.WriteImage(new_seg, os.path.join(new_seg_dir, new_seg_name))

        print('{} have {} slice left'.format(ct_file, seg_array.shape[0]))
        left_slice_list.append(ct_array.shape[0])

        # 在轴向上按照一定的步长进行切块取样，并将结果保存为nii数据

        # 每处理完一个数据，打印一次已经使用的时间
        print('already use {:.3f} min'.format((time() - start_time) / 60))
        print('-----------')


def process_lits():
    root = '/workspace/mnt/group/alg-pro/yankai/segment/data/LITS/training/'

    new_ct_dir = '/workspace/mnt/group/alg-pro/yankai/segment/data/pre_process'
    new_seg_dir = '/workspace/mnt/group/alg-pro/yankai/segment/data/pre_process'

    file_list = [file for file in os.listdir(root) if 'volume' in file]
    for ct_file in file_list:
        ct_dir = os.path.join(root, ct_file)
        seg_dir = os.path.join(root, ct_file.replace('volume', 'segmentation'))

        # ct_dir = os.path.join(root + ct_file, 'PATIENT_DICOM')
        # seg_dir = os.path.join(os.path.join(root + ct_file, 'MASKS_DICOM'), 'liver')
        file_index = 0

        # 用来统计最终剩下的slice数量
        left_slice_list = []

        start_time = time()
        print("process:", ct_file)
        # 将CT和金标准入读内存
        # ct = sitk.ReadImage(os.path.join(ct_dir, ct_file), sitk.sitkInt16)
        ct = read_dicom(ct_dir)
        ct_array = sitk.GetArrayFromImage(ct)

        # seg = sitk.ReadImage(os.path.join(seg_dir, ct_file.replace('volume', 'segmentation')), sitk.sitkInt8)
        seg = read_dicom(seg_dir)
        seg_array = sitk.GetArrayFromImage(seg)

        # 将金标准中肝脏和肝肿瘤的标签融合为一个
        # seg_array[seg_array > 0] = 1

        # 将灰度值在阈值之外的截断掉
        ct_array[ct_array > upper] = upper
        ct_array[ct_array < lower] = lower

        # 对CT和金标准进行插值，插值之后的array依然是int类型
        print("process chazhi")

        ct_array = ndimage.zoom(ct_array, (ct.GetSpacing()[-1] / slice_thickness, down_scale, down_scale), order=3)
        seg_array = ndimage.zoom(seg_array, (ct.GetSpacing()[-1] / slice_thickness, down_scale, down_scale), order=0)

        print(ct_array.shape)
        print(seg_array.shape)

        new_ct = sitk.GetImageFromArray(ct_array)

        new_ct.SetDirection(ct.GetDirection())
        new_ct.SetOrigin(ct.GetOrigin())
        new_ct.SetSpacing(
            (ct.GetSpacing()[0] * int(1 / down_scale), ct.GetSpacing()[1] * int(1 / down_scale), slice_thickness))

        new_seg = sitk.GetImageFromArray(seg_array)
        new_seg.SetDirection(ct.GetDirection())
        new_seg.SetOrigin(ct.GetOrigin())
        new_seg.SetSpacing(
            (ct.GetSpacing()[0] * int(1 / down_scale), ct.GetSpacing()[1] * int(1 / down_scale), slice_thickness))

        # new_ct_name = 'volume-' + str(int(ct_file.split('.')[-1])+130) + '.nii'
        # new_seg_name = 'segmentation-' + str(int(ct_file.split('.')[-1])+130) + '.nii'
        new_ct_name = 'volume-' + re.sub('\D', '', ct_file) + '.nii'

        new_seg_name = new_ct_name.replace('volume', 'segmentation')

        print("write ", new_ct_name)
        print("write ", new_seg_name)
        sitk.WriteImage(new_ct, os.path.join(new_ct_dir, new_ct_name))
        sitk.WriteImage(new_seg, os.path.join(new_seg_dir, new_seg_name))

        print('{} have {} slice left'.format(ct_file, seg_array.shape[0]))
        left_slice_list.append(ct_array.shape[0])

        # 在轴向上按照一定的步长进行切块取样，并将结果保存为nii数据

        # 每处理完一个数据，打印一次已经使用的时间
        print('already use {:.3f} min'.format((time() - start_time) / 60))
        print('-----------')


def process_sliver07():
    root = "/workspace/mnt/group/alg-pro/yankai/segment/data/sliver07"

    new_ct_dir = '/workspace/mnt/group/alg-pro/yankai/segment/data/pre_process'
    new_seg_dir = '/workspace/mnt/group/alg-pro/yankai/segment/data/pre_process'

    file_list = [file for file in os.listdir(root) if 'orig' in file and 'mhd' in file]
    for ct_file in file_list:
        ct_dir = os.path.join(root, ct_file)
        seg_dir = os.path.join(root, ct_file.replace('orig', 'seg'))

        # ct_dir = os.path.join(root + ct_file, 'PATIENT_DICOM')
        # seg_dir = os.path.join(os.path.join(root + ct_file, 'MASKS_DICOM'), 'liver')
        file_index = 0

        # 用来统计最终剩下的slice数量
        left_slice_list = []

        start_time = time()
        print("process:", ct_file)
        # 将CT和金标准入读内存
        # ct = sitk.ReadImage(os.path.join(ct_dir, ct_file), sitk.sitkInt16)
        ct = read_dicom(ct_dir)
        ct_array = sitk.GetArrayFromImage(ct)

        # seg = sitk.ReadImage(os.path.join(seg_dir, ct_file.replace('volume', 'segmentation')), sitk.sitkInt8)
        seg = read_dicom(seg_dir)
        seg_array = sitk.GetArrayFromImage(seg)

        # 将金标准中肝脏和肝肿瘤的标签融合为一个
        # seg_array[seg_array > 0] = 1

        # 将灰度值在阈值之外的截断掉
        ct_array[ct_array > upper] = upper
        ct_array[ct_array < lower] = lower

        # 对CT和金标准进行插值，插值之后的array依然是int类型
        print("process chazhi")

        ct_array = ndimage.zoom(ct_array, (ct.GetSpacing()[-1] / slice_thickness, down_scale, down_scale), order=3)
        seg_array = ndimage.zoom(seg_array, (ct.GetSpacing()[-1] / slice_thickness, down_scale, down_scale), order=0)

        print(ct_array.shape)
        print(seg_array.shape)

        new_ct = sitk.GetImageFromArray(ct_array)

        new_ct.SetDirection(ct.GetDirection())
        new_ct.SetOrigin(ct.GetOrigin())
        new_ct.SetSpacing(
            (ct.GetSpacing()[0] * int(1 / down_scale), ct.GetSpacing()[1] * int(1 / down_scale), slice_thickness))

        new_seg = sitk.GetImageFromArray(seg_array)
        new_seg.SetDirection(ct.GetDirection())
        new_seg.SetOrigin(ct.GetOrigin())
        new_seg.SetSpacing(
            (ct.GetSpacing()[0] * int(1 / down_scale), ct.GetSpacing()[1] * int(1 / down_scale), slice_thickness))

        # new_ct_name = 'volume-' + str(int(ct_file.split('.')[-1])+130) + '.nii'
        # new_seg_name = 'segmentation-' + str(int(ct_file.split('.')[-1])+130) + '.nii'
        new_ct_name = 'volume-' + str(int(re.sub('\D', '', ct_file)) + 130) + '.nii'

        new_seg_name = new_ct_name.replace('volume', 'segmentation')

        print("write ", new_ct_name)
        print("write ", new_seg_name)
        sitk.WriteImage(new_ct, os.path.join(new_ct_dir, new_ct_name))
        sitk.WriteImage(new_seg, os.path.join(new_seg_dir, new_seg_name))

        print('{} have {} slice left'.format(ct_file, seg_array.shape[0]))
        left_slice_list.append(ct_array.shape[0])

        # 在轴向上按照一定的步长进行切块取样，并将结果保存为nii数据

        # 每处理完一个数据，打印一次已经使用的时间
        print('already use {:.3f} min'.format((time() - start_time) / 60))
        print('-----------')

def process_lung():
    root = '/workspace/mnt/group/alg-pro/yankai/segment/data/test_data/'

    new_ct_dir = '/workspace/mnt/group/alg-pro/yankai/segment/data/lung_pre_process/'
    new_seg_dir = '/workspace/mnt/group/alg-pro/yankai/segment/data/lung_pre_process/'
    file_list = [file for file in os.listdir(root)]
    for i,ct_file in enumerate(file_list):
        ct_dir = os.path.join(root + ct_file, 'original1')
        seg_dir = os.path.join(root + ct_file, 'vein')

        seg = read_dicom(seg_dir)
        seg_array = sitk.GetArrayFromImage(seg)
        seg_array[seg_array == 255] = 1

        file_index = 0

        # 用来统计最终剩下的slice数量
        left_slice_list = []

        start_time = time()
        print("process:", ct_file)
        # 将CT和金标准入读内存
        # ct = sitk.ReadImage(os.path.join(ct_dir, ct_file), sitk.sitkInt16)
        ct = read_dicom(ct_dir)
        ct = set_Window(ct,1024,0)
        ct_array = sitk.GetArrayFromImage(ct)

        # seg = sitk.ReadImage(os.path.join(seg_dir, ct_file.replace('volume', 'segmentation')), sitk.sitkInt8)

        # 将金标准中肝脏和肝肿瘤的标签融合为一个
        # seg_array[seg_array > 0] = 1

        # 将灰度值在阈值之外的截断掉
        # ct_array[ct_array > upper] = upper
        # ct_array[ct_array < lower] = lower



        # 对CT和金标准进行插值，插值之后的array依然是int类型
        print("process chazhi")

        ct_array = ndimage.zoom(ct_array, (ct.GetSpacing()[-1] / slice_thickness, down_scale, down_scale), order=3)
        seg_array = ndimage.zoom(seg_array, (ct.GetSpacing()[-1] / slice_thickness, down_scale, down_scale), order=0)

        # 找到肝脏区域开始和结束的slice，并各向外扩张
        # z = np.any(seg_array, axis=(1, 2))
        # start_slice, end_slice = np.where(z)[0][[0, -1]]
        #
        # # 两个方向上各扩张个slice
        # if start_slice - expand_slice < 0:
        #     start_slice = 0
        # else:
        #     start_slice -= expand_slice
        #
        # if end_slice + expand_slice >= seg_array.shape[0]:
        #     end_slice = seg_array.shape[0] - 1
        # else:
        #     end_slice += expand_slice
        #
        # # 如果这时候剩下的slice数量不足size，直接放弃，这样的数据很少
        # if end_slice - start_slice + 1 < size:
        #     print('!!!!!!!!!!!!!!!!')
        #     print(ct_file, 'too little slice')
        #     print('!!!!!!!!!!!!!!!!')
        #     continue
        #
        # new_ct_array = ct_array[start_slice:end_slice + 1, :, :]
        # new_seg_array = seg_array[start_slice:end_slice + 1, :, :]

        new_ct = sitk.GetImageFromArray(ct_array)

        new_ct.SetDirection(ct.GetDirection())
        new_ct.SetOrigin(ct.GetOrigin())
        new_ct.SetSpacing(
            (ct.GetSpacing()[0] * int(1 / down_scale), ct.GetSpacing()[1] * int(1 / down_scale), slice_thickness))

        new_seg = sitk.GetImageFromArray(seg_array)
        new_seg.SetDirection(ct.GetDirection())
        new_seg.SetOrigin(ct.GetOrigin())
        new_seg.SetSpacing(
            (ct.GetSpacing()[0] * int(1 / down_scale), ct.GetSpacing()[1] * int(1 / down_scale), slice_thickness))

        new_ct_name = 'volume-' + str(i+30) + '.nii'
        new_seg_name = new_ct_name.replace('volume','segmentation')

        print("write ", new_ct_name)
        print("write ", new_seg_name)
        sitk.WriteImage(new_ct, os.path.join(new_ct_dir, new_ct_name))
        sitk.WriteImage(new_seg, os.path.join(new_seg_dir, new_seg_name))

        print('{} have {} slice left'.format(ct_file, seg_array.shape[0]))
        left_slice_list.append(ct_array.shape[0])

        # 在轴向上按照一定的步长进行切块取样，并将结果保存为nii数据

        # 每处理完一个数据，打印一次已经使用的时间
        print('already use {:.3f} min'.format((time() - start_time) / 60))
        print('-----------')


process_lung()
#process_sliver07()
#process_3d()
# process_lits()
