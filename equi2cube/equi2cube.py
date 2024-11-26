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

class Equi2CubeConverter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Equirectangular to Cubemap Converter")
        self.root.geometry("600x500")
        
        # 用于存储配置的变量
        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.is_converting = False
        self.conversion_thread = None
        self.message_queue = queue.Queue()
        
        self.create_gui()
        self.load_config()
        
        # 定期检查消息队列
        self.root.after(100, self.check_message_queue)

    def create_gui(self):
        # 输入文件夹选择
        input_frame = ttk.Frame(self.root)
        input_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(input_frame, text="输入文件夹:").pack(side='left')
        ttk.Entry(input_frame, textvariable=self.input_dir).pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(input_frame, text="浏览", command=self.select_input_dir).pack(side='right')

        # 输出文件夹选择
        output_frame = ttk.Frame(self.root)
        output_frame.pack(fill='x', padx=5, pady=5)
        ttk.Label(output_frame, text="输出文件夹:").pack(side='left')
        ttk.Entry(output_frame, textvariable=self.output_dir).pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(output_frame, text="浏览", command=self.select_output_dir).pack(side='right')

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_label = ttk.Label(self.root, text="0/0")
        self.progress_label.pack(pady=5)
        self.progress_bar = ttk.Progressbar(self.root, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill='x', padx=5, pady=5)

        # Log窗口
        self.log_text = scrolledtext.ScrolledText(self.root, height=15)
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)

        # 按钮框架
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill='x', padx=5, pady=5)
        
        self.convert_button = ttk.Button(button_frame, text="转换", command=self.toggle_conversion)
        self.convert_button.pack(side='left', padx=5)
        
        ttk.Button(button_frame, text="退出", command=self.on_closing).pack(side='right', padx=5)

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

    def save_config(self):
        config_path = Path.home() / '.equi2cube_config.json'
        config = {
            'input_dir': self.input_dir.get(),
            'output_dir': self.output_dir.get()
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
                
                # 保存每个面
                stem = image_file.stem  # 获取文件名（不含扩展名）
                ext = image_file.suffix  # 获取扩展名
                for face, suffix in zip(faces, suffixes):
                    # 新的文件名格式：原文件名_方向后缀.扩展名
                    output_file = output_path / f"{stem}_{suffix}{ext}"
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