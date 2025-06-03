import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import threading
import os
import cv2
import time
import json
import argparse
import sys
from pathlib import Path
import re
import glob

def show_help():
    help_text = """
图像序列帧转视频工具使用说明:

GUI模式:
    image2video.exe
    直接双击运行，通过界面操作

命令行模式:
    image2video.exe [参数]

参数说明:
    -i, --input       输入图像序列文件夹路径
    -o, --output      输出视频文件路径
    -f, --fps         帧率 (默认30)
    -t, --type        输出格式 (mp4/avi, 默认mp4)
    -?, --help        显示帮助信息

示例:
    image2video.exe -i images_folder -o output.mp4 -f 30 -t mp4
    """
    print(help_text)
    return help_text

class ImageToVideoConverter:
    def __init__(self, master=None, args=None):
        # 初始化转换状态
        self.is_converting = False
        self.image_dir = None
        self.should_stop = False
        
        # 获取当前脚本所在目录
        self.script_dir = Path(__file__).parent
        
        if master:
            self.setup_gui(master)
            if args:
                self.apply_args(args)
        elif args:
            self.process_command_line(args)

    def setup_gui(self, master):
        self.master = master
        self.master.title("图像序列帧转换为视频")
        
        # 设置窗口最小大小和默认大小
        self.master.minsize(800, 500)
        self.master.geometry("800x400")
        
        # 创建主框架
        main_frame = ttk.Frame(master, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 输入目录选择
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=3)
        ttk.Label(input_frame, text="输入目录:").pack(side=tk.LEFT)
        self.input_entry = ttk.Entry(input_frame)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(input_frame, text="选择文件夹", command=self.browse_input_directory).pack(side=tk.LEFT)
        ttk.Button(input_frame, text="打开文件夹", command=self.open_input_directory).pack(side=tk.LEFT, padx=(5,0))
        
        # 文件过滤器
        filter_frame = ttk.Frame(main_frame)
        filter_frame.pack(fill=tk.X, pady=3)
        ttk.Label(filter_frame, text="文件过滤器:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar(value="*.png")
        self.filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var)
        self.filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 文件排序方式
        sort_frame = ttk.Frame(main_frame)
        sort_frame.pack(fill=tk.X, pady=3)
        ttk.Label(sort_frame, text="排序方式:").pack(side=tk.LEFT)
        self.sort_var = tk.StringVar(value="natural")
        sort_options = ttk.Combobox(sort_frame, textvariable=self.sort_var, state="readonly", 
                                  values=["natural", "alphabetical", "timestamp"])
        sort_options.pack(side=tk.LEFT, padx=5)
        
        # 输出文件设置
        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill=tk.X, pady=3)
        ttk.Label(output_frame, text="输出文件:").pack(side=tk.LEFT)
        self.output_file = tk.StringVar()
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_file)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(output_frame, text="选择文件", command=self.browse_output_file).pack(side=tk.LEFT)
        
        # 视频设置
        video_settings_frame = ttk.Frame(main_frame)
        video_settings_frame.pack(fill=tk.X, pady=3)
        
        # 帧率设置
        ttk.Label(video_settings_frame, text="帧率:").pack(side=tk.LEFT)
        self.fps_var = tk.StringVar(value="30")
        self.fps_entry = ttk.Entry(video_settings_frame, width=6, textvariable=self.fps_var)
        self.fps_entry.pack(side=tk.LEFT, padx=(5, 15))
        
        # 输出格式选择
        ttk.Label(video_settings_frame, text="输出格式:").pack(side=tk.LEFT)
        self.format_var = tk.StringVar(value='mp4')
        ttk.Radiobutton(video_settings_frame, text='MP4', variable=self.format_var, value='mp4').pack(side=tk.LEFT, padx=(5, 5))
        ttk.Radiobutton(video_settings_frame, text='AVI', variable=self.format_var, value='avi').pack(side=tk.LEFT)
        
        # 编解码器选择
        codec_frame = ttk.Frame(main_frame)
        codec_frame.pack(fill=tk.X, pady=3)
        ttk.Label(codec_frame, text="编解码器:").pack(side=tk.LEFT)
        self.codec_var = tk.StringVar(value="AUTO")
        codec_options = ttk.Combobox(codec_frame, textvariable=self.codec_var, state="readonly", 
                                   values=["AUTO", "H264", "XVID", "MJPG", "DIVX", "MP4V"])
        codec_options.pack(side=tk.LEFT, padx=5)
        
        # 分辨率设置
        resolution_frame = ttk.Frame(main_frame)
        resolution_frame.pack(fill=tk.X, pady=3)
        ttk.Label(resolution_frame, text="分辨率:").pack(side=tk.LEFT)
        self.width_var = tk.StringVar(value="")
        self.height_var = tk.StringVar(value="")
        ttk.Label(resolution_frame, text="宽:").pack(side=tk.LEFT, padx=(5, 0))
        self.width_entry = ttk.Entry(resolution_frame, width=6, textvariable=self.width_var)
        self.width_entry.pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(resolution_frame, text="高:").pack(side=tk.LEFT)
        self.height_entry = ttk.Entry(resolution_frame, width=6, textvariable=self.height_var)
        self.height_entry.pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(resolution_frame, text="(留空将使用第一张图片的分辨率)").pack(side=tk.LEFT)
        
        # 进度条
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=3)
        self.progress = ttk.Progressbar(progress_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill=tk.X)
        
        # 日志输出
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=3)
        self.log_text = tk.Text(log_frame, height=8)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        # 底部按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10,0))
        ttk.Button(button_frame, text="退出", command=self.on_closing).pack(side=tk.LEFT)
        self.start_button = ttk.Button(button_frame, text="开始转换", command=self.toggle_conversion)
        self.start_button.pack(side=tk.RIGHT)
        
        # 加载配置
        self.load_config()
        
    def browse_input_directory(self):
        directory = filedialog.askdirectory(title="选择图像序列文件夹")
        if directory:
            self.image_dir = directory
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, directory)
            
            # 自动生成输出文件名（基于文件夹名称）
            folder_name = os.path.basename(directory)
            if not self.output_file.get():
                output_file = os.path.join(os.path.dirname(directory), f"{folder_name}.{self.format_var.get()}")
                self.output_file.set(output_file)

    def browse_output_file(self):
        output_format = self.format_var.get().lower()
        file_types = [("视频文件", f"*.{output_format}"), ("所有文件", "*.*")]
        file = filedialog.asksaveasfilename(title="保存视频文件", defaultextension=f".{output_format}", filetypes=file_types)
        if file:
            self.output_file.set(file)

    def open_input_directory(self):
        input_dir = self.input_entry.get()
        if input_dir and os.path.exists(input_dir):
            if os.name == 'nt':  # Windows
                os.startfile(input_dir)
            else:  # macOS 和 Linux
                import subprocess
                subprocess.run(['xdg-open' if os.name == 'posix' else 'open', input_dir])
        else:
            messagebox.showwarning("警告", "输入目录不存在")
            
    def toggle_conversion(self):
        if not self.is_converting:
            # 开始转换
            if not self.image_dir or not os.path.isdir(self.image_dir):
                messagebox.showerror("错误", "请选择输入图像序列文件夹")
                return
                
            if not self.output_file.get():
                messagebox.showerror("错误", "请指定输出视频文件")
                return
            
            # 清空日志
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(tk.END, "开始转换...\n")
            self.progress['value'] = 0  # 重置进度条
            
            # 更新状态和按钮文字
            self.is_converting = True
            self.should_stop = False
            self.start_button.config(text="停止转换")
            
            # 启动后台线程
            threading.Thread(target=self.convert_images_to_video).start()
        else:
            # 停止转换
            self.should_stop = True
            self.log_text.insert(tk.END, "正在停止转换...\n")
            self.log_text.see(tk.END)
        
    def try_create_video_writer(self, output_file, fourcc, fps, size):
        """尝试创建VideoWriter对象，如果失败则尝试其他编解码器"""
        # 首先尝试指定的编解码器
        writer = cv2.VideoWriter(output_file, fourcc, fps, size)
        if writer.isOpened():
            return writer, fourcc
        
        # 如果失败，尝试其他常用编解码器
        codec_options = []
        
        # 根据输出格式选择适当的编解码器
        if output_file.lower().endswith('.mp4'):
            codec_options = [
                ('mp4v', cv2.VideoWriter_fourcc(*'mp4v')),  # MP4V
                ('avc1', cv2.VideoWriter_fourcc(*'avc1')),  # H264
                ('H264', cv2.VideoWriter_fourcc(*'H264')),  # H264 另一种写法
                ('X264', cv2.VideoWriter_fourcc(*'X264')),  # X264
                ('DIVX', cv2.VideoWriter_fourcc(*'DIVX')),  # DIVX
            ]
        elif output_file.lower().endswith('.avi'):
            codec_options = [
                ('XVID', cv2.VideoWriter_fourcc(*'XVID')),  # XVID
                ('MJPG', cv2.VideoWriter_fourcc(*'MJPG')),  # Motion JPEG
                ('DIVX', cv2.VideoWriter_fourcc(*'DIVX')),  # DIVX
                ('I420', cv2.VideoWriter_fourcc(*'I420')),  # Uncompressed YUV
            ]
        
        # 尝试其他编解码器
        for codec_name, codec_fourcc in codec_options:
            writer = cv2.VideoWriter(output_file, codec_fourcc, fps, size)
            if writer.isOpened():
                self.log_text.insert(tk.END, f"使用备选编解码器: {codec_name}\n")
                self.log_text.see(tk.END)
                return writer, codec_fourcc
        
        return None, None
    
    def get_codec_fourcc(self, codec_name, output_format):
        """获取编解码器的fourcc代码"""
        codec_map = {
            "H264": "avc1",
            "XVID": "XVID",
            "MJPG": "MJPG",
            "DIVX": "DIVX",
            "MP4V": "mp4v"
        }
        
        # 如果选择AUTO，根据输出格式自动选择
        if codec_name == "AUTO":
            if output_format.lower() == 'mp4':
                return cv2.VideoWriter_fourcc(*'mp4v')  # MP4V 通常兼容性更好
            else:  # avi
                return cv2.VideoWriter_fourcc(*'XVID')
        else:
            # 使用指定的编解码器
            fourcc_code = codec_map.get(codec_name, "mp4v")
            return cv2.VideoWriter_fourcc(*fourcc_code)
    
    def convert_images_to_video(self):
        try:
            input_dir = self.image_dir
            output_file = self.output_file.get()
            pattern = self.filter_var.get()
            fps = int(self.fps_var.get() or "30")
            sort_method = self.sort_var.get()
            selected_codec = self.codec_var.get()
            output_format = self.format_var.get()
            
            # 获取所有匹配的图像文件
            image_files = glob.glob(os.path.join(input_dir, pattern))
            
            if not image_files:
                self.log_text.insert(tk.END, f"未找到匹配的图像文件: {pattern}\n")
                self.log_text.see(tk.END)
                self.is_converting = False
                self.start_button.config(text="开始转换")
                return
                
            # 根据选择的排序方法排序文件
            if sort_method == "natural":
                # 自然排序（考虑数字序列）
                image_files.sort(key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
            elif sort_method == "alphabetical":
                # 字母顺序排序
                image_files.sort()
            elif sort_method == "timestamp":
                # 按文件修改时间排序
                image_files.sort(key=os.path.getmtime)
                
            self.log_text.insert(tk.END, f"找到 {len(image_files)} 个图像文件\n")
            self.log_text.see(tk.END)
            
            # 获取编解码器fourcc代码
            fourcc = self.get_codec_fourcc(selected_codec, output_format)
            
            # 检查目录是否存在，如果不存在则创建
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            # 确定视频分辨率
            width = self.width_var.get().strip()
            height = self.height_var.get().strip()
            
            # 如果未指定分辨率，使用第一张图片的分辨率
            if not (width and height):
                first_img = cv2.imread(image_files[0])
                if first_img is None:
                    self.log_text.insert(tk.END, f"无法读取图像: {image_files[0]}\n")
                    self.is_converting = False
                    self.start_button.config(text="开始转换")
                    return
                    
                h, w = first_img.shape[:2]
                self.log_text.insert(tk.END, f"使用图像分辨率: {w}x{h}\n")
            else:
                try:
                    w = int(width)
                    h = int(height)
                    self.log_text.insert(tk.END, f"使用自定义分辨率: {w}x{h}\n")
                except ValueError:
                    self.log_text.insert(tk.END, "分辨率格式无效，必须是整数\n")
                    self.is_converting = False
                    self.start_button.config(text="开始转换")
                    return
                    
            # 创建 VideoWriter 对象
            self.log_text.insert(tk.END, f"创建视频文件: {output_file}\n")
            self.log_text.insert(tk.END, f"使用编解码器: {selected_codec}\n")
            
            # 尝试创建VideoWriter，如果失败则尝试备选方案
            video_writer, used_fourcc = self.try_create_video_writer(output_file, fourcc, fps, (w, h))
            
            if video_writer is None or not video_writer.isOpened():
                self.log_text.insert(tk.END, f"无法创建输出视频文件: {output_file}\n")
                self.log_text.insert(tk.END, f"请尝试其他编解码器或确保相关编解码器已安装\n")
                self.log_text.insert(tk.END, f"如果使用H264编解码器，可能需要下载OpenH264库: https://github.com/cisco/openh264/releases\n")
                
                self.is_converting = False
                self.start_button.config(text="开始转换")
                return
            
            # 设置进度条
            self.progress['maximum'] = len(image_files)
            
            start_time = time.time()
            processed_count = 0
            
            # 开始处理图像
            for i, img_file in enumerate(image_files):
                if self.should_stop:
                    break
                    
                img = cv2.imread(img_file)
                if img is None:
                    self.log_text.insert(tk.END, f"无法读取图像: {img_file}\n")
                    self.log_text.see(tk.END)
                    continue
                
                # 调整图像大小以匹配视频分辨率
                if img.shape[1] != w or img.shape[0] != h:
                    img = cv2.resize(img, (w, h))
                
                # 写入帧
                video_writer.write(img)
                processed_count += 1
                
                # 更新进度
                self.progress['value'] = i + 1
                if (i + 1) % 10 == 0 or (i + 1) == len(image_files):
                    self.log_text.insert(tk.END, f"处理中: {i+1}/{len(image_files)} 帧\n")
                    self.log_text.see(tk.END)
                
                # 更新UI
                self.master.update_idletasks()
            
            # 释放资源
            video_writer.release()
            
            # 计算处理时间
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = elapsed_time % 60
            
            if not self.should_stop:
                self.log_text.insert(tk.END, f"\n处理完成!\n")
                self.log_text.insert(tk.END, f"输出文件: {output_file}\n")
                self.log_text.insert(tk.END, f"处理了 {processed_count} 帧图像\n")
                self.log_text.insert(tk.END, f"视频帧率: {fps} fps\n")
                self.log_text.insert(tk.END, f"分辨率: {w}x{h}\n")
                self.log_text.insert(tk.END, f"编解码器: {selected_codec}\n")
                self.log_text.insert(tk.END, f"总用时: {minutes}分 {seconds:.1f}秒\n")
                
                # 检查文件是否成功创建
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    self.log_text.insert(tk.END, f"视频文件已成功创建\n")
                else:
                    self.log_text.insert(tk.END, f"警告: 输出文件可能未正确创建或为空\n")
            else:
                self.log_text.insert(tk.END, f"\n转换已停止\n")
                self.log_text.insert(tk.END, f"已处理 {processed_count} 帧图像\n")
            
            self.log_text.see(tk.END)
            
        except Exception as e:
            self.log_text.insert(tk.END, f"处理失败: {str(e)}\n")
            import traceback
            self.log_text.insert(tk.END, f"错误详情: {traceback.format_exc()}\n")
            self.log_text.see(tk.END)
        finally:
            self.is_converting = False
            self.should_stop = False
            self.start_button.config(text="开始转换")
            self.save_config()

    def load_config(self):
        """从配置文件加载设置"""
        config_path = self.script_dir / 'config.json'
        if config_path.exists():
            try:
                with open(config_path, encoding='utf-8') as f:
                    config = json.load(f)
                    # 基本设置
                    self.image_dir = config.get("image_dir", "")
                    if self.image_dir:
                        self.input_entry.delete(0, tk.END)
                        self.input_entry.insert(0, self.image_dir)
                        
                    self.output_file.set(config.get("output_file", ""))
                    self.filter_var.set(config.get("filter", "*.png"))
                    self.sort_var.set(config.get("sort_method", "natural"))
                    
                    # 视频设置
                    self.fps_var.set(config.get("fps", "30"))
                    self.format_var.set(config.get("format", "mp4"))
                    self.codec_var.set(config.get("codec", "AUTO"))
                    
                    # 分辨率设置
                    self.width_var.set(config.get("width", ""))
                    self.height_var.set(config.get("height", ""))
                    
            except Exception as e:
                print(f"加载配置文件时出错: {str(e)}")
    
    def save_config(self):
        """保存设置到配置文件"""
        config_path = self.script_dir / 'config.json'
        config = {
            # 基本设置
            "image_dir": self.image_dir,
            "output_file": self.output_file.get(),
            "filter": self.filter_var.get(),
            "sort_method": self.sort_var.get(),
            
            # 视频设置
            "fps": self.fps_var.get(),
            "format": self.format_var.get(),
            "codec": self.codec_var.get(),
            
            # 分辨率设置
            "width": self.width_var.get(),
            "height": self.height_var.get(),
        }
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存配置文件时出错: {str(e)}")

    def on_closing(self):
        # 确保关闭时停止转换
        self.should_stop = True
        self.save_config()
        self.master.destroy()

    def apply_args(self, args):
        """将命令行参数用到GUI"""
        if args.input:
            self.image_dir = args.input
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, args.input)
        if args.output:
            self.output_file.set(args.output)
        if args.fps:
            self.fps_var.set(str(args.fps))
        if args.type:
            self.format_var.set(args.type.lower())

    def process_command_line(self, args):
        """处理命令行模式的转换"""
        if not all([args.input, args.output]):
            print("错误: 需要指定输入目录和输出视频文件")
            return
        
        input_dir = args.input
        output_file = args.output
        fps = args.fps or 30
        output_format = args.type.lower() if args.type else 'mp4'
        
        if not os.path.isdir(input_dir):
            print(f"错误: 输入目录不存在: {input_dir}")
            return
        
        # 获取所有图像文件
        image_files = glob.glob(os.path.join(input_dir, "*.png"))
        if not image_files:
            image_files = glob.glob(os.path.join(input_dir, "*.jpg"))
        
        if not image_files:
            print("错误: 输入目录中未找到图像文件")
            return
            
        print(f"开始转换...")
        print(f"输入目录: {input_dir}")
        print(f"找到 {len(image_files)} 个图像文件")
        print(f"输出文件: {output_file}")
        print(f"帧率: {fps}")
        
        # 自然排序文件
        image_files.sort(key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
        
        # 获取第一张图片的尺寸
        first_img = cv2.imread(image_files[0])
        if first_img is None:
            print(f"错误: 无法读取图像: {image_files[0]}")
            return
            
        h, w = first_img.shape[:2]
        print(f"图像分辨率: {w}x{h}")
        
        # 确定输出编解码器，尝试多种编解码器
        video_writer = None
        used_codec = None
        
        if output_format == 'mp4':
            codecs = [('mp4v', cv2.VideoWriter_fourcc(*'mp4v')), 
                      ('avc1', cv2.VideoWriter_fourcc(*'avc1')), 
                      ('DIVX', cv2.VideoWriter_fourcc(*'DIVX'))]
        else:  # avi
            codecs = [('XVID', cv2.VideoWriter_fourcc(*'XVID')), 
                      ('MJPG', cv2.VideoWriter_fourcc(*'MJPG')), 
                      ('DIVX', cv2.VideoWriter_fourcc(*'DIVX'))]
        
        # 创建输出目录（如果不存在）
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 尝试每个编解码器
        for codec_name, fourcc in codecs:
            video_writer = cv2.VideoWriter(output_file, fourcc, fps, (w, h))
            if video_writer.isOpened():
                used_codec = codec_name
                print(f"使用编解码器: {codec_name}")
                break
        
        if not video_writer or not video_writer.isOpened():
            print(f"错误: 无法创建输出视频文件: {output_file}")
            print("请尝试其他编解码器或格式")
            print("如果使用H264编解码器，可能需要下载OpenH264库: https://github.com/cisco/openh264/releases")
            return
            
        start_time = time.time()
        processed_count = 0
        
        # 开始处理图像
        for i, img_file in enumerate(image_files):
            img = cv2.imread(img_file)
            if img is None:
                print(f"无法读取图像: {img_file}")
                continue
            
            # 写入帧
            video_writer.write(img)
            processed_count += 1
            
            # 定期显示进度
            if (i + 1) % 100 == 0:
                print(f"已处理: {i+1}/{len(image_files)} 帧")
        
        # 释放资源
        video_writer.release()
        
        # 计算处理时间
        elapsed_time = time.time() - start_time
        
        print(f"处理完成: {processed_count} 帧, 耗时 {elapsed_time:.2f} 秒")
        print(f"输出文件: {output_file}")
        print(f"使用编解码器: {used_codec}")
        
        # 检查文件是否成功创建
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            print(f"视频文件已成功创建")
        else:
            print(f"警告: 输出文件可能未正确创建或为空")

def main():
    parser = argparse.ArgumentParser(description='图像序列帧转视频工具', add_help=False)
    parser.add_argument('-i', '--input', help='输入图像序列文件夹路径')
    parser.add_argument('-o', '--output', help='输出视频文件路径')
    parser.add_argument('-f', '--fps', type=int, help='帧率 (默认30)')
    parser.add_argument('-t', '--type', choices=['mp4', 'avi'], help='输出格式 (mp4/avi)')
    parser.add_argument('-?', '--help', action='store_true', help='显示帮助信息')

    args = parser.parse_args()

    if args.help:
        show_help()
        return

    # 如果没有参数，启动GUI模式
    if len(sys.argv) == 1:
        root = tk.Tk()
        app = ImageToVideoConverter(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    else:
        # 命令行模式
        ImageToVideoConverter(args=args)

if __name__ == "__main__":
    main() 