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
from datetime import timedelta

def show_help():
    help_text = """
视频转图像序列帧工具使用说明:

GUI模式:
    video2image.exe
    直接双击运行，通过界面操作

命令行模式:
    video2image.exe [参数]

参数说明:
    -i, --input        输入视频文件路径
    -o, --output       输出目录路径
    -f, --fps         帧率 (每秒输出几帧, 默认1)
    -t, --type        输出格式 (jpg/png, 默认jpg)
    -?, --help        显示帮助信息

示例:
    video2image.exe -i video.mp4 -o output_folder -f 2 -t jpg
    """
    print(help_text)
    return help_text

class VideoToImageConverter:
    def __init__(self, master=None, args=None):
        # 初始化转换状态
        self.is_converting = False
        self.video_file = None
        
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
        self.master.title("视频转换为图像序列帧")
        
        # 设置窗口最小大小和默认大小
        self.master.minsize(800, 400)
        self.master.geometry("800x400")
        
        # 创建主框架
        main_frame = ttk.Frame(master, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 输入源选择
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=3)
        ttk.Label(input_frame, text="输入源:").pack(side=tk.LEFT)
        self.input_entry = ttk.Entry(input_frame)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(input_frame, text="选择文件", command=lambda: self.browse_video(True)).pack(side=tk.LEFT)
        ttk.Button(input_frame, text="选择文件夹", command=lambda: self.browse_video(False)).pack(side=tk.LEFT, padx=(5,0))
        
        # 输出目录设置
        output_frame = ttk.Frame(main_frame)
        output_frame.pack(fill=tk.X, pady=3)
        ttk.Label(output_frame, text="输出目录:").pack(side=tk.LEFT)
        self.output_dir = tk.StringVar()
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_dir)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(output_frame, text="选择文件夹", command=self.select_output_directory).pack(side=tk.LEFT)
        ttk.Button(output_frame, text="打开文件夹", command=self.open_output_directory).pack(side=tk.LEFT, padx=(5,0))
        
        # 清空输出目录选项
        clear_frame = ttk.Frame(main_frame)
        clear_frame.pack(fill=tk.X, pady=3)
        self.clear_output = tk.BooleanVar(value=False)
        ttk.Checkbutton(clear_frame, text="清空输出目录", variable=self.clear_output).pack(side=tk.LEFT)
        
        # 文件命名设置行
        naming_frame = ttk.Frame(main_frame)
        naming_frame.pack(fill=tk.X, pady=3)

        # 前缀设置
        ttk.Label(naming_frame, text="文件名前缀:").pack(side=tk.LEFT)
        self.prefix_input = ttk.Entry(naming_frame, width=10)
        self.prefix_input.pack(side=tk.LEFT, padx=(5, 15))
        self.prefix_input.insert(0, "")  # 默认为空，完全由用户决定前缀

        # 起始数设置
        ttk.Label(naming_frame, text="起始序号:").pack(side=tk.LEFT)
        self.start_num_input = ttk.Entry(naming_frame, width=6)
        self.start_num_input.pack(side=tk.LEFT, padx=(5, 15))
        self.start_num_input.insert(0, "1")

        # 序号位数设置
        ttk.Label(naming_frame, text="序号位数:").pack(side=tk.LEFT)
        self.num_digits_input = ttk.Entry(naming_frame, width=6)
        self.num_digits_input.pack(side=tk.LEFT, padx=5)
        self.num_digits_input.insert(0, "4")
        
        # 输出格式选择
        format_frame = ttk.Frame(main_frame)
        format_frame.pack(fill=tk.X, pady=3)
        ttk.Label(format_frame, text="输出格式:").pack(side=tk.LEFT)
        self.format_var = tk.StringVar(value='jpg')
        ttk.Radiobutton(format_frame, text='JPG', variable=self.format_var, value='jpg').pack(side=tk.LEFT)
        ttk.Radiobutton(format_frame, text='PNG', variable=self.format_var, value='png').pack(side=tk.LEFT)
        
        # 时间和帧率设置
        time_fps_frame = ttk.Frame(main_frame)
        time_fps_frame.pack(fill=tk.X, pady=3)

        # 开始时间
        self.start_time_label = ttk.Label(time_fps_frame, text="开始时间(秒):")
        self.start_time_label.pack(side=tk.LEFT)
        self.start_time_input = ttk.Entry(time_fps_frame, width=8)
        self.start_time_input.pack(side=tk.LEFT, padx=(5, 15))
        self.start_time_input.insert(0, "0")

        # 结束时间
        self.end_time_label = ttk.Label(time_fps_frame, text="结束时间(秒):")
        self.end_time_label.pack(side=tk.LEFT)
        self.end_time_input = ttk.Entry(time_fps_frame, width=8)
        self.end_time_input.pack(side=tk.LEFT, padx=(5, 15))
        self.end_time_input.insert(0, "")  # 默认空表示到视频结束

        # 帧率
        ttk.Label(time_fps_frame, text="帧率:").pack(side=tk.LEFT)
        self.fps_entry = ttk.Entry(time_fps_frame, width=8)
        self.fps_entry.pack(side=tk.LEFT, padx=5)
        
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
        
    def browse_video(self, is_file):
        if is_file:
            file = filedialog.askopenfilename(
                title="选择视频文件",
                filetypes=(("视文件", "*.mp4;*.avi"), ("所有文件", "*.*"))
            )
            if file:
                self.video_file = file
                self.input_entry.delete(0, tk.END)
                self.input_entry.insert(0, file)
        else:
            directory = filedialog.askdirectory(title="选择视频文件夹")
            if directory:
                self.video_file = directory
                self.input_entry.delete(0, tk.END)
                self.input_entry.insert(0, directory)

    def select_output_directory(self):
        directory = filedialog.askdirectory(title="选择输出目录")
        self.output_dir.set(directory)
        
    def toggle_conversion(self):
        if not self.is_converting:
            # 开始转换
            if not self.video_file:
                messagebox.showerror("错误", "请选择输入视频文件")
                return
                
            # 清空日志
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(tk.END, "开始转换...\n")
            self.progress['value'] = 0  # 重置进度条
            
            # 设置进度条最大值
            cap = cv2.VideoCapture(self.video_file)
            self.progress['maximum'] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            
            # 更新状态和按钮文字
            self.is_converting = True
            self.start_button.config(text="停止转换")
            
            # 启动后台线程
            threading.Thread(target=self.convert_video).start()
        else:
            # 停止转换
            self.is_converting = False
            self.start_button.config(text="开始转换")
            self.log_text.insert(tk.END, "转换已停止\n")
            self.log_text.see(tk.END)
        
    def convert_video(self):
        try:
            # 获取开始和结束时间
            start_time = float(self.start_time_input.get() or "0")
            end_time_text = self.end_time_input.get()
            
            cap = cv2.VideoCapture(self.video_file)
            if not cap.isOpened():
                self.log_text.insert(tk.END, f"无法打开视频文件: {self.video_file}\n")
                self.is_converting = False
                self.start_button.config(text="开始转换")
                return
            
            # 获取视频总时长（秒）
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            total_seconds = total_frames / video_fps
            
            # 处理结束时间
            end_time = float(end_time_text) if end_time_text.strip() else total_seconds
            
            # 验证时间输入
            if start_time < 0 or end_time > total_seconds or start_time >= end_time:
                self.log_text.insert(tk.END, 
                    f"时间设置无效！\n视频总长: {total_seconds:.1f}秒\n"
                    f"请确保: 0 ≤ 开始时间 < 结束时间 ≤ {total_seconds:.1f}\n")
                cap.release()
                self.is_converting = False
                self.start_button.config(text="开始转换")
                return
            
            # 设置起始帧位置
            start_frame = int(start_time * video_fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            # 计算需要处理的总帧数
            end_frame = int(end_time * video_fps)
            self.progress['maximum'] = end_frame - start_frame
            
            fps = int(self.fps_entry.get()) if self.fps_entry.get().isdigit() else 1
            frame_interval = int(video_fps / fps)
            output_format = self.format_var.get()
            output_path = self.output_dir.get()
            
            frame_count = 0
            saved_count = 0
            start_process_time = time.time()
            
            self.log_text.insert(tk.END, 
                f"开始时间: {start_time:.1f}秒\n"
                f"结束时间: {end_time:.1f}秒\n"
                f"帧率设置: {fps} fps\n"
                f"输出格式: {output_format}\n"
                f"输出目录: {output_path}\n")
            
            # 检查并清空输出目录
            if not output_path:
                self.log_text.insert(tk.END, "请选择输出目录\n")
                self.is_converting = False
                self.start_button.config(text="开始转换")
                return

            # 确保输出目录存在
            os.makedirs(output_path, exist_ok=True)

            # 如果选择了清空输出目录
            if self.clear_output.get():
                try:
                    for file in os.listdir(output_path):
                        file_path = os.path.join(output_path, file)
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                    self.log_text.insert(tk.END, "已清空输出目录\n")
                except Exception as e:
                    self.log_text.insert(tk.END, f"清空输出目录时出错: {str(e)}\n")
                    self.is_converting = False
                    self.start_button.config(text="开始转换")
                    return

            # 获取文件命名相关设置
            prefix = self.prefix_input.get()
            try:
                start_num = int(self.start_num_input.get() or "1")
                num_digits = int(self.num_digits_input.get() or "4")
            except ValueError:
                self.log_text.insert(tk.END, "起始序号和序号位数必须是整数\n")
                self.is_converting = False
                self.start_button.config(text="开始转换")
                return

            while cap.isOpened() and self.is_converting:
                ret, frame = cap.read()
                if not ret or frame_count >= (end_frame - start_frame):
                    break
                
                if frame_count % frame_interval == 0:
                    # 生成文件名：前缀_序号.格式
                    frame_num = start_num + saved_count
                    frame_filename = os.path.join(
                        output_path, 
                        f"{prefix}{frame_num:0{num_digits}d}.{output_format}"
                    )
                    success, encoded_img = cv2.imencode(f'.{output_format}', frame)
                    if success:
                        with open(frame_filename, 'wb') as f:
                            encoded_img.tofile(f)
                    saved_count += 1
                
                frame_count += 1
                self.progress['value'] = frame_count
                
            cap.release()
            
            if self.is_converting:
                elapsed_time = time.time() - start_process_time
                self.log_text.insert(tk.END, 
                    f"处理完成!\n"
                    f"时间段: {start_time:.1f}s - {end_time:.1f}s\n"
                    f"共保存: {saved_count} 帧\n"
                    f"耗时: {elapsed_time:.2f} 秒\n")
                self.progress['value'] = self.progress['maximum']
            
            self.is_converting = False
            self.start_button.config(text="开始转换")
            self.log_text.see(tk.END)
            
        except ValueError as e:
            self.log_text.insert(tk.END, "请输入有效的数值\n")
            self.is_converting = False
            self.start_button.config(text="开始转换")
        except Exception as e:
            self.log_text.insert(tk.END, f"处理失败: {str(e)}\n")
            self.is_converting = False
            self.start_button.config(text="开始转换")

    def reset(self):
        self.video_file = ""
        self.input_entry.delete(0, tk.END)
        self.output_dir.set("")
        self.fps_entry.delete(0, tk.END)
        self.log_text.delete(1.0, tk.END)
        self.progress['value'] = 0
        # 确保重时也重置转换状态
        self.is_converting = False
        self.start_button.config(text="开始转换")

    def load_config(self):
        """从配置文件加载设置"""
        config_path = self.script_dir / 'config.json'
        if config_path.exists():
            try:
                with open(config_path, encoding='utf-8') as f:
                    config = json.load(f)
                    # 基本设置
                    self.output_dir.set(config.get("output_dir", ""))
                    self.fps_entry.insert(0, config.get("fps", "1"))
                    self.video_file = config.get("video_file", "")
                    if self.video_file:
                        self.input_entry.insert(0, self.video_file)
                    
                    # 清空输出目录选项
                    self.clear_output.set(config.get("clear_output", False))
                    
                    # 文件命名设置
                    self.prefix_input.delete(0, tk.END)
                    self.prefix_input.insert(0, config.get("prefix", ""))
                    self.start_num_input.delete(0, tk.END)
                    self.start_num_input.insert(0, config.get("start_num", "1"))
                    self.num_digits_input.delete(0, tk.END)
                    self.num_digits_input.insert(0, config.get("num_digits", "4"))
                    
                    # 输出格式
                    self.format_var.set(config.get("format", "jpg"))
                    
                    # 时间设置
                    self.start_time_input.delete(0, tk.END)
                    self.start_time_input.insert(0, config.get("start_time", "0"))
                    self.end_time_input.delete(0, tk.END)
                    self.end_time_input.insert(0, config.get("end_time", ""))
                    
            except Exception as e:
                print(f"加载配置文件时出错: {str(e)}")
    
    def save_config(self):
        """保存设置到配置文件"""
        config_path = self.script_dir / 'config.json'
        config = {
            # 基本设置
            "output_dir": self.output_dir.get(),
            "fps": self.fps_entry.get(),
            "video_file": self.video_file,
            
            # 清空输出目录选项
            "clear_output": self.clear_output.get(),
            
            # 文件命名设置
            "prefix": self.prefix_input.get(),
            "start_num": self.start_num_input.get(),
            "num_digits": self.num_digits_input.get(),
            
            # 输出格式
            "format": self.format_var.get(),
            
            # 时间设置
            "start_time": self.start_time_input.get(),
            "end_time": self.end_time_input.get(),
        }
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存配置文件时出错: {str(e)}")

    def on_closing(self):
        # 确保关闭时停止转换
        self.is_converting = False
        self.save_config()
        self.master.destroy()

    def apply_args(self, args):
        """将命令行数用到GUI"""
        if args.input:
            self.video_file = args.input
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, args.input)
        if args.output:
            self.output_dir.set(args.output)
        if args.fps:
            self.fps_entry.delete(0, tk.END)
            self.fps_entry.insert(0, str(args.fps))
        if args.type:
            self.format_var.set(args.type.lower())

    def process_command_line(self, args):
        """处理命令行模式的转换"""
        if not all([args.input, args.output]):
            print("错误: 需要指定输入文件和输出目录")
            return

        self.video_file = args.input
        output_path = args.output
        fps = args.fps or 1
        output_format = args.type.lower() if args.type else 'jpg'

        # 确保输出目录存在
        os.makedirs(output_path, exist_ok=True)

        print(f"开始转换...")
        print(f"输入文件: {self.video_file}")
        print(f"输出目录: {output_path}")
        print(f"帧率: {fps}")
        print(f"输出格式: {output_format}")

        cap = cv2.VideoCapture(self.video_file)
        if not cap.isOpened():
            print(f"错误: 无法打开视频文件: {self.video_file}")
            return

        video_fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = int(video_fps / fps)
        
        frame_count = 0
        saved_count = 0
        start_time = time.time()
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                frame_filename = os.path.join(output_path, f"frame_{saved_count:04d}.{output_format}")
                # 命令行模式也需要修改保存方式
                success, encoded_img = cv2.imencode(f'.{output_format}', frame)
                if success:
                    with open(frame_filename, 'wb') as f:
                        encoded_img.tofile(f)
                saved_count += 1
            
            frame_count += 1
            if frame_count % 100 == 0:
                print(f"已处理: {frame_count} 帧")
        
        cap.release()
        elapsed_time = time.time() - start_time
        print(f"处理完成: {saved_count} 帧, 耗时 {elapsed_time:.2f} 秒")

    def open_output_directory(self):
        output_dir = self.output_dir.get()
        if output_dir and os.path.exists(output_dir):
            if os.name == 'nt':  # Windows
                os.startfile(output_dir)
            else:  # macOS 和 Linux
                import subprocess
                subprocess.run(['xdg-open' if os.name == 'posix' else 'open', output_dir])
        else:
            messagebox.showwarning("警告", "输出目录不存在")

def main():
    parser = argparse.ArgumentParser(description='视频转图像序列帧工具', add_help=False)
    parser.add_argument('-i', '--input', help='输入视频文件路径')
    parser.add_argument('-o', '--output', help='输出目录路径')
    parser.add_argument('-f', '--fps', type=int, help='帧率 (每秒输出几帧)')
    parser.add_argument('-t', '--type', choices=['jpg', 'png'], help='输出格式 (jpg/png)')
    parser.add_argument('-?', '--help', action='store_true', help='显示帮助信息')

    args = parser.parse_args()

    if args.help:
        show_help()
        return

    # 如果没有参数，启动GUI模式
    if len(sys.argv) == 1:
        root = tk.Tk()
        app = VideoToImageConverter(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()
    else:
        # 命令行模式
        VideoToImageConverter(args=args)

if __name__ == "__main__":
    main()
