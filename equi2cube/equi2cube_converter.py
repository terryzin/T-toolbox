import numpy as np
from PIL import Image

def create_cubemap_matrices(width):
    """创建立方体贴图的采样矩阵"""
    # 创建网格坐标
    x = np.linspace(-1, 1, width)
    y = np.linspace(-1, 1, width)
    x, y = np.meshgrid(x, y)

    # 通过将 x 取反来实现水平翻转
    matrices = {
        'posy': (-x, -np.ones_like(y), y),         # 上
        'negy': (-x, np.ones_like(y), -y),         # 下
        'negx': (np.ones_like(x), y, x),           # 左
        'posz': (-x, y, np.ones_like(x)),          # 前
        'posx': (-np.ones_like(x), y, -x),         # 右
        'negz': (x, y, -np.ones_like(x))           # 后
    }
    
    return matrices

def convert_xyz_to_equirect(x, y, z, height, width):
    """将3D坐标转换为等距柱状投影坐标"""
    # 计算球面坐标
    theta = np.arctan2(z, x)  # 经度 [-pi, pi]
    phi = np.arctan2(y, np.sqrt(x**2 + z**2))  # 纬度 [-pi/2, pi/2]
    
    # 转换到图像坐标 [0, width-1] x [0, height-1]
    u = (theta + np.pi) * width / (2 * np.pi)
    v = (phi + np.pi/2) * height / np.pi
    
    return u, v

def equirectangular_to_cubemap(equi_img, face_size=None):
    """
    将等距柱状投影图像转换为立方体贴图
    
    Args:
        equi_img: PIL Image对象，输入的等距柱状投影图像
        face_size: 输出的立方体每个面的大小，默认为输入图像高度的1/2
        
    Returns:
        tuple: 包含6个PIL Image对象的元组 (front, back, left, right, top, bottom)
    """
    # 转换为numpy数组
    equi_array = np.array(equi_img)
    height, width = equi_array.shape[:2]
    
    # 如果没有指定face_size，设置默认值
    if face_size is None:
        face_size = height // 2
        
    # 创建采样矩阵
    matrices = create_cubemap_matrices(face_size)
    faces_raw = {}
    
    # 对每个面进行转换
    for face_name, (x, y, z) in matrices.items():
        # 标准化向量
        norm = np.sqrt(x**2 + y**2 + z**2)
        x, y, z = x/norm, y/norm, z/norm
        
        # 计算采样坐标
        u, v = convert_xyz_to_equirect(x, y, z, height, width)
        
        # 使用双线性插值进行采样
        u = np.clip(u, 0, width - 1)
        v = np.clip(v, 0, height - 1)
        
        # 整数部分和小数部分
        u0, v0 = np.floor(u).astype(int), np.floor(v).astype(int)
        u1, v1 = np.ceil(u).astype(int), np.ceil(v).astype(int)
        
        # 确保索引不越界
        u1 = np.clip(u1, 0, width - 1)
        v1 = np.clip(v1, 0, height - 1)
        
        # 计算权重
        wu = u - u0
        wv = v - v0
        
        # 修改这里：调整权重的维度以匹配图像数据
        wu = wu[..., np.newaxis]
        wv = wv[..., np.newaxis]
        
        # 双线性插值
        face_pixels = (
            (1 - wu) * (1 - wv) * equi_array[v0, u0] +
            wu * (1 - wv) * equi_array[v0, u1] +
            (1 - wu) * wv * equi_array[v1, u0] +
            wu * wv * equi_array[v1, u1]
        ).astype(np.uint8)
        
        faces_raw[face_name] = Image.fromarray(face_pixels)
    
    # 在返回之前对所有面进行水平翻转，并对顶面和底面进行旋转
    return (
        faces_raw['posy'].rotate(-90, expand=True),    # 上(逆时针90度)
        faces_raw['negx'],    # 左
        faces_raw['posz'],    # 前
        faces_raw['posx'],    # 右
        faces_raw['negz'],    # 后
        faces_raw['negy'].rotate(90, expand=True)   # 下(顺时针90度)
    ) 