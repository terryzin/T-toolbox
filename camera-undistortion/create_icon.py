from PIL import Image, ImageDraw
import os

def create_camera_icon():
    # 创建一个256x256的图像，使用RGBA模式支持透明度
    size = 256
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # 设置颜色
    camera_color = (41, 128, 185)  # 蓝色
    lens_color = (52, 152, 219)    # 浅蓝色
    highlight_color = (255, 255, 255, 128)  # 半透明白色
    
    # 计算相机主体尺寸
    body_width = int(size * 0.7)
    body_height = int(size * 0.5)
    body_x = (size - body_width) // 2
    body_y = (size - body_height) // 2
    
    # 绘制相机主体（圆角矩形）
    corner_radius = int(size * 0.1)
    draw.rounded_rectangle(
        [body_x, body_y, body_x + body_width, body_y + body_height],
        corner_radius,
        fill=camera_color
    )
    
    # 绘制镜头（圆形）
    lens_radius = int(size * 0.2)
    lens_x = size // 2
    lens_y = size // 2
    draw.ellipse(
        [lens_x - lens_radius, lens_y - lens_radius,
         lens_x + lens_radius, lens_y + lens_radius],
        fill=lens_color
    )
    
    # 绘制镜头内部（小圆）
    inner_lens_radius = int(lens_radius * 0.7)
    draw.ellipse(
        [lens_x - inner_lens_radius, lens_y - inner_lens_radius,
         lens_x + inner_lens_radius, lens_y + inner_lens_radius],
        fill=(0, 0, 0, 255)
    )
    
    # 添加高光效果
    highlight_radius = int(lens_radius * 0.3)
    highlight_x = lens_x - int(lens_radius * 0.3)
    highlight_y = lens_y - int(lens_radius * 0.3)
    draw.ellipse(
        [highlight_x - highlight_radius, highlight_y - highlight_radius,
         highlight_x + highlight_radius, highlight_y + highlight_radius],
        fill=highlight_color
    )
    
    # 确保assets目录存在
    if not os.path.exists('assets'):
        os.makedirs('assets')
    
    # 保存图标
    image.save('assets/camera-undistortion.png')
    print("图标已创建: assets/camera-undistortion.png")

if __name__ == "__main__":
    create_camera_icon() 