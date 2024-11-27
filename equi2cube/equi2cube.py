import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import json
import os
from PIL import Image
import numpy as np
from pathlib import Path
import time
from threading import Thread
import queue
import equi2cube_converter
from PIL import ImageTk
import tkinter.ttk as ttk

class Equi2CubeConverter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Equirectangular to Cubemap Converter")
        
        # 设置最小窗口大小
        self.root.minsize(800, 900)
        
        # 默认窗口大小
        self.root.geometry("800x900")
        
        # 允许窗口调整大小
        self.root.resizable(True, True)
        
        # 用于存储配置的变量
        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.is_converting = False
        self.conversion_thread = None
        self.message_queue = queue.Queue()
        
        # 添加面选择配置
        self.face_config = {
            'posy': {'name': '上面(Top)', 'enabled': True},
            'negx': {'name': '左面(Left)', 'enabled': True},
            'posz': {'name': '前面(Front)', 'enabled': True},
            'posx': {'name': '右面(Right)', 'enabled': True},
            'negz': {'name': '后面(Back)', 'enabled': True},
            'negy': {'name': '下面(Bottom)', 'enabled': True}
        }
        
        # 预览图像的大小
        self.preview_size = 150
        
        # 创建预览图像的字典
        self.preview_labels = {}
        
        # Add this line to initialize progress_var
        self.progress_var = tk.DoubleVar()
        
        self.create_gui()
        self.load_config()
        
        # 定期检查消息队列
        self.root.after(100, self.check_message_queue)

    def create_gui(self):
        # 主容器使用网格布局
        main_container = ttk.Frame(self.root, padding="10")
        main_container.pack(fill='both', expand=True)

        # 输入文件夹选择 (row 0)
        input_frame = ttk.Frame(main_container)
        input_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(input_frame, text="输入文件夹:").pack(side='left')
        ttk.Entry(input_frame, textvariable=self.input_dir).pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(input_frame, text="浏览", command=self.select_input_dir).pack(side='right')

        # 输出文件夹选择 (row 1)
        output_frame = ttk.Frame(main_container)
        output_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(output_frame, text="输出文件夹:").pack(side='left')
        ttk.Entry(output_frame, textvariable=self.output_dir).pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(output_frame, text="浏览", command=self.select_output_dir).pack(side='right')

        # 面选择框架 (row 2)
        face_select_frame = ttk.LabelFrame(main_container, text="输出面选择")
        face_select_frame.pack(fill='x', pady=(0, 5))
        
        # 使用网格布局排列复选框，每行3个
        self.face_vars = {}
        for i, (face_id, face_info) in enumerate(self.face_config.items()):
            var = tk.BooleanVar(value=face_info['enabled'])
            self.face_vars[face_id] = var
            cb = ttk.Checkbutton(
                face_select_frame,
                text=face_info['name'],
                variable=var,
                command=self.save_config
            )
            cb.grid(row=i//3, column=i%3, padx=5, pady=2, sticky='w')

        # 预览框架 (row 3)
        preview_frame = ttk.LabelFrame(main_container, text="预览")
        preview_frame.pack(fill='both', pady=(0, 5))
        
        preview_grid = ttk.Frame(preview_frame)
        preview_grid.pack(expand=True, padx=5, pady=5)
        
        # 预览标签布局
        positions = {
            'posy': (0, 1),  # 上
            'negx': (1, 0),  # 左
            'posz': (1, 1),  # 前
            'posx': (1, 2),  # 右
            'negz': (1, 3),  # 后
            'negy': (2, 1)   # 下
        }
        
        self.preview_labels = {}
        for face_id, (row, col) in positions.items():
            frame = ttk.Frame(
                preview_grid,
                width=self.preview_size,
                height=self.preview_size,
                relief='solid',
                borderwidth=1
            )
            frame.grid(row=row, column=col, padx=2, pady=2)
            frame.grid_propagate(False)
            
            label = ttk.Label(frame, text=self.face_config[face_id]['name'])
            label.pack(expand=True)
            self.preview_labels[face_id] = label

        # 进度显示 (row 4)
        progress_frame = ttk.Frame(main_container)
        progress_frame.pack(fill='x', pady=(0, 5))
        self.progress_label = ttk.Label(progress_frame, text="0/0")
        self.progress_label.pack()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill='x')

        # Log窗口 (row 5)
        log_frame = ttk.LabelFrame(main_container, text="处理日志")
        log_frame.pack(fill='both', expand=True, pady=(0, 5))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8)
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)

        # 控制按钮 (row 6)
        button_frame = ttk.Frame(main_container)
        button_frame.pack(fill='x')
        ttk.Button(button_frame, text="退出", command=self.on_closing).pack(side='left', padx=5)
        self.convert_button = ttk.Button(button_frame, text="转换", command=self.toggle_conversion)
        self.convert_button.pack(side='right', padx=5)

    def select_input_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.input_dir.set(directory)
            self.save_config()

    def select_output_dir(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir.set(directory)
            self.save_config()

    def load_config(self):
        config_path = Path.home() / '.equi2cube_config.json'
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                self.input_dir.set(config.get('input_dir', ''))
                self.output_dir.set(config.get('output_dir', ''))
                
                # 加载面选择配置
                if 'face_config' in config:
                    for face_id, enabled in config['face_config'].items():
                        if face_id in self.face_config:
                            self.face_config[face_id]['enabled'] = enabled

    def save_config(self):
        config_path = Path.home() / '.equi2cube_config.json'
        config = {
            'input_dir': self.input_dir.get(),
            'output_dir': self.output_dir.get(),
            'face_config': {
                face_id: var.get()
                for face_id, var in self.face_vars.items()
            }
        }
        with open(config_path, 'w') as f:
            json.dump(config, f)

    def log_message(self, message):
        self.message_queue.put(message)

    def check_message_queue(self):
        while not self.message_queue.empty():
            message = self.message_queue.get()
            self.log_text.insert(tk.END, message + '\n')
            self.log_text.see(tk.END)
        self.root.after(100, self.check_message_queue)

    def toggle_conversion(self):
        if not self.is_converting:
            if not self.input_dir.get() or not self.output_dir.get():
                self.log_message("请选择输入和输出文件夹")
                return
            
            self.is_converting = True
            self.convert_button.configure(text="停止")
            self.conversion_thread = Thread(target=self.convert_images)
            self.conversion_thread.start()
        else:
            self.is_converting = False
            self.convert_button.configure(text="转换")

    def update_preview(self, faces):
        """更新预览图像"""
        for face_id, face in zip(['posy', 'negx', 'posz', 'posx', 'negz', 'negy'], faces):
            if face_id in self.preview_labels:
                # 调整图像大小用于预览
                preview_image = face.copy()
                preview_image.thumbnail((self.preview_size, self.preview_size))
                
                # 转换为PhotoImage
                photo = ImageTk.PhotoImage(preview_image)
                
                # 更新标签
                label = self.preview_labels[face_id]
                label.configure(image=photo)
                label.image = photo  # 保持引用以防止垃圾回收

    def convert_images(self):
        start_time = time.time()
        input_path = Path(self.input_dir.get())
        output_path = Path(self.output_dir.get())
        
        # 确保输出目录存在
        output_path.mkdir(parents=True, exist_ok=True)
        
        image_files = list(input_path.glob("*.jpg")) + list(input_path.glob("*.png"))
        total_files = len(image_files)
        
        self.log_message(f"找到 {total_files} 个图像文件")
        processed_count = 0
        
        # 修改这里：更新文件名后缀
        suffixes = ['pz', 'nz', 'nx', 'px', 'py', 'ny']
        
        for i, image_file in enumerate(image_files, 1):
            if not self.is_converting:
                break
            
            try:
                self.log_message(f"处理: {image_file.name}")
                
                # 读取图像
                img = Image.open(image_file)
                
                # 转换图像
                faces = equi2cube_converter.equirectangular_to_cubemap(img)
                
                # 更新预览
                self.update_preview(faces)
                
                # 根据选择保存需要的面
                stem = image_file.stem
                ext = image_file.suffix
                for face, face_id in zip(faces, ['posy', 'negx', 'posz', 'posx', 'negz', 'negy']):
                    if self.face_vars[face_id].get():  # 只保存选中的面
                        output_file = output_path / f"{stem}_{face_id}{ext}"
                        face.save(output_file)
                
                processed_count += 1
                
            except Exception as e:
                self.log_message(f"处理 {image_file.name} 时出错: {str(e)}")
                continue
            
            # 更新进度
            progress = (i / total_files) * 100
            self.progress_var.set(progress)
            self.progress_label.configure(text=f"{i}/{total_files}")
        
        end_time = time.time()
        duration = end_time - start_time
        self.log_message(f"\n转换完成！")
        self.log_message(f"成功处理: {processed_count}/{total_files} 个文件")
        self.log_message(f"耗时: {duration:.2f} 秒")
        
        self.is_converting = False
        self.convert_button.configure(text="转换")

    def on_closing(self):
        self.save_config()
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

if __name__ == "__main__":
    app = Equi2CubeConverter()
    app.run() 