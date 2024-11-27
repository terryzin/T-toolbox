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
import cv2
import argparse
import sys
import concurrent.futures

class Equi2CubeConverter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Equirectangular to Cubemap Converter")
        
        # 设置最小窗口大小
        self.root.minsize(800, 850)
        
        # 默认窗口大小
        self.root.geometry("800x850")
        
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
        self.preview_size = 100
        
        # 创建预览图像的字典
        self.preview_labels = {}
        
        # Add this line to initialize progress_var
        self.progress_var = tk.DoubleVar()
        
        # 添加清空文件夹选项的变量
        self.clear_output_dir = tk.BooleanVar(value=False)
        
        # 获取当前脚本所在目录
        self.script_dir = Path(__file__).parent
        
        self.create_gui()
        self.load_config()
        
        # 定期检查消息队列
        self.root.after(100, self.check_message_queue)

    def create_gui(self):
        # 主容器使用网格布局
        main_container = ttk.Frame(self.root, padding="10")
        main_container.pack(fill='both', expand=True)

        # 输入源选择 (row 0)
        input_frame = ttk.Frame(main_container)
        input_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(input_frame, text="输入源:").pack(side='left')
        ttk.Entry(input_frame, textvariable=self.input_dir).pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(input_frame, text="选择文件夹", command=self.select_input_dir).pack(side='right')
        ttk.Button(input_frame, text="选择文件", command=self.select_input_file).pack(side='right', padx=5)

        # 输出文件夹选择 (row 1)
        output_frame = ttk.Frame(main_container)
        output_frame.pack(fill='x', pady=(0, 5))
        ttk.Label(output_frame, text="输出文件夹:").pack(side='left')
        ttk.Entry(output_frame, textvariable=self.output_dir).pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(output_frame, text="打开文件夹", command=self.open_output_dir).pack(side='right')
        ttk.Button(output_frame, text="选择文件夹", command=self.select_output_dir).pack(side='right', padx=5)

        # 修改输出文件夹选择后的布局
        settings_frame = ttk.Frame(main_container)
        settings_frame.pack(fill='x', pady=(0, 5))
        
        # 清空输出目录选项左对齐
        ttk.Checkbutton(
            settings_frame,
            text="清空输出目录",
            variable=self.clear_output_dir,
            command=self.save_config
        ).pack(side='left')
        
        # 线程数设置右对齐
        right_settings = ttk.Frame(settings_frame)
        right_settings.pack(side='right')
        
        ttk.Label(right_settings, text="处理线程数:").pack(side='left')
        self.thread_count = tk.StringVar(value="1")
        thread_entry = ttk.Entry(right_settings, textvariable=self.thread_count, width=5)
        thread_entry.pack(side='left', padx=5)

        # 面选择框架放在下一行
        face_select_frame = ttk.LabelFrame(main_container, text="输出面选择")
        face_select_frame.pack(fill='x', pady=(0, 5))
        
        # 使用水平布局排列复选框
        face_box_frame = ttk.Frame(face_select_frame)
        face_box_frame.pack(padx=5, pady=2)
        
        self.face_vars = {}
        for i, (face_id, face_info) in enumerate(self.face_config.items()):
            var = tk.BooleanVar(value=face_info['enabled'])
            self.face_vars[face_id] = var
            cb = ttk.Checkbutton(
                face_box_frame,
                text=face_info['name'],
                variable=var,
                command=self.save_config
            )
            cb.pack(side='left', padx=5)

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
        self.log_text = scrolledtext.ScrolledText(log_frame, height=5)
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)

        # 控制按钮 (row 6)
        button_frame = ttk.Frame(main_container)
        button_frame.pack(fill='x')
        ttk.Button(button_frame, text="退出", command=self.on_closing).pack(side='left', padx=5)
        self.convert_button = ttk.Button(button_frame, text="转换", command=self.toggle_conversion)
        self.convert_button.pack(side='right', padx=5)

    def select_input_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[
                ("图像文件", "*.jpg;*.jpeg;*.png"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.input_dir.set(file_path)
            self.save_config()

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
        """从配置文件加载设置"""
        config_path = self.script_dir / 'config.json'
        if config_path.exists():
            try:
                with open(config_path, encoding='utf-8') as f:
                    config = json.load(f)
                    self.input_dir.set(config.get('input_dir', ''))
                    self.output_dir.set(config.get('output_dir', ''))
                    self.clear_output_dir.set(config.get('clear_output_dir', False))
                    self.thread_count.set(config.get('thread_count', '1'))  # 加载线程数配置
                    
                    # 加载面选择配置
                    if 'face_config' in config:
                        for face_id, enabled in config['face_config'].items():
                            if face_id in self.face_config:
                                self.face_config[face_id]['enabled'] = enabled
            except Exception as e:
                print(f"加载配置文件时出错: {str(e)}")

    def save_config(self):
        """保存设置到配置文件"""
        config_path = self.script_dir / 'config.json'
        config = {
            'input_dir': self.input_dir.get(),
            'output_dir': self.output_dir.get(),
            'clear_output_dir': self.clear_output_dir.get(),
            'face_config': {
                face_id: var.get()
                for face_id, var in self.face_vars.items()
            },
            'thread_count': self.thread_count.get()  # 添加线程数配置
        }
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存配置文件时出错: {str(e)}")

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
        try:
            # 获取线程数
            try:
                thread_count = max(1, min(32, int(self.thread_count.get())))
            except ValueError:
                thread_count = 1
                self.thread_count.set("1")

            input_path = Path(self.input_dir.get())
            output_path = Path(self.output_dir.get())
            
            # 确保输出目录存在
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 如果选择了清空输出文件夹，则在处理前清空
            if self.clear_output_dir.get():
                try:
                    # 删除文件夹中的所有文件
                    for file in output_path.glob("*"):
                        if file.is_file():
                            file.unlink()
                    self.log_message("已清空输出文件夹")
                except Exception as e:
                    self.log_message(f"清空输出文件夹时出错: {str(e)}")
                    return
            
            # 根据输入是文件还是目录来确定要处理的文件列表
            if input_path.is_file():
                # 如果是单个文件，直接将其作为待处理文件
                if input_path.suffix.lower() in {'.jpg', '.jpeg', '.png'}:
                    image_files = [input_path]
                else:
                    self.log_message(f"错误：不支持的文件格式 {input_path.suffix}")
                    return
            else:
                # 如果是目录，获取所有支持的图像文件
                image_files = list(input_path.glob("*.jpg")) + list(input_path.glob("*.jpeg")) + list(input_path.glob("*.png"))
            
            total_files = len(image_files)
            if total_files == 0:
                self.log_message("没有找到可处理的图像文件")
                return
            
            self.log_message(f"开始处理 {total_files} 个图像文件")
            processed_count = 0
            
            # 修改这里：更新文件名后缀
            suffixes = ['pz', 'nz', 'nx', 'px', 'py', 'ny']
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count) as executor:
                # 创建任务列表
                futures = []
                for i, image_file in enumerate(image_files):
                    if not self.is_converting:
                        break
                    
                    future = executor.submit(self.process_single_image, image_file, output_path)
                    futures.append(future)

                # 处理完成的任务
                for i, future in enumerate(concurrent.futures.as_completed(futures)):
                    if not self.is_converting:
                        # 取消所有未完成的任务
                        for f in futures:
                            f.cancel()
                        break

                    try:
                        result = future.result()
                        if result:
                            processed_count += 1
                    except Exception as e:
                        self.log_message(f"处理任务时出错: {str(e)}")

                    # 更新进度
                    progress = ((i + 1) / total_files) * 100
                    self.progress_var.set(progress)
                    self.progress_label.configure(text=f"{i+1}/{total_files}")

            # 计算处理时间
            end_time = time.time()
            duration = end_time - start_time
            
            # 输出汇总信息
            self.log_message(f"\n转换完成！")
            self.log_message(f"成功处理: {processed_count}/{total_files} 个文件")
            self.log_message(f"处理线程: {thread_count} 个")
            self.log_message(f"耗时: {int(duration//60)}分 {duration%60:.1f}秒")

        except Exception as e:
            self.log_message(f"发生错误: {str(e)}")
        finally:
            self.is_converting = False
            self.convert_button.configure(text="转换")

    def process_single_image(self, image_file, output_path):
        try:
            self.log_message(f"处理: {image_file.name}")
            
            # 读取图像
            img = Image.open(image_file)
            
            # 转换图像
            faces = equi2cube_converter.equirectangular_to_cubemap(img)
            
            # 只在单线程模式下更新预览
            if int(self.thread_count.get()) == 1:
                self.root.after(0, lambda: self.update_preview(faces))
            
            # 保存需要的面
            stem = image_file.stem
            ext = image_file.suffix
            for face, face_id in zip(faces, ['posy', 'negx', 'posz', 'posx', 'negz', 'negy']):
                if self.face_vars[face_id].get():  # 只保存选中的面
                    output_file = output_path / f"{stem}_{face_id}{ext}"
                    face.save(output_file)
            
            return True
            
        except Exception as e:
            self.log_message(f"处理 {image_file.name} 时出错: {str(e)}")
            return False

    def on_closing(self):
        self.save_config()
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def open_output_dir(self):
        """打开输出文件夹"""
        output_dir = self.output_dir.get()
        if output_dir and os.path.exists(output_dir):
            # 使用系统默认的文件管理器打开文件夹
            os.startfile(output_dir) if os.name == 'nt' else os.system(f'xdg-open "{output_dir}"')
        else:
            self.log_message("输出文件夹不存在")

def process_single_file(input_path, output_dir):
    """处理单个文件"""
    # 原有的文件处理逻辑...
    try:
        img = cv2.imread(str(input_path))
        if img is None:
            print(f"无法读取文件: {input_path}")
            return
        # 处理图片的其他代码...
        output_path = Path(output_dir) / input_path.name
        cv2.imwrite(str(output_path), result)
        print(f"已处理: {input_path.name}")
    except Exception as e:
        print(f"处理文件 {input_path} 时出错: {str(e)}")

def process_directory(input_dir, output_dir):
    """处理���个文件夹"""
    input_path = Path(input_dir)
    supported_extensions = {'.jpg', '.jpeg', '.png'}
    
    for file_path in input_path.glob('*'):
        if file_path.suffix.lower() in supported_extensions:
            process_single_file(file_path, output_dir)

def main():
    # Check if any command line arguments were provided
    if len(sys.argv) > 1:
        # Command-line mode
        parser = argparse.ArgumentParser(description='全景图转立方体贴图工具')
        parser.add_argument('input', help='输入源 (可以是单个文件或文件夹)')
        parser.add_argument('output', help='输出文件夹')
        args = parser.parse_args()

        input_path = Path(args.input)
        output_dir = Path(args.output)

        # 确保输出目录存在
        output_dir.mkdir(parents=True, exist_ok=True)

        if input_path.is_file():
            process_single_file(input_path, output_dir)
        elif input_path.is_dir():
            process_directory(input_path, output_dir)
        else:
            print(f"错误: 输入源 '{input_path}' 不存在或无效")
            return 1
    else:
        # GUI mode
        converter = Equi2CubeConverter()
        converter.run()

    return 0

if __name__ == '__main__':
    sys.exit(main()) 