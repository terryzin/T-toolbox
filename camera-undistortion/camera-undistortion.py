import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import threading
from pathlib import Path
import concurrent.futures
import time
import numpy as np
import cv2
import xml.etree.ElementTree as ET
import re

class CameraUndistortion:
    def __init__(self, root):
        self.root = root
        self.root.title("相机图像反畸变工具")
        
        # 配置文件路径
        self.config_file = "camera-undistortion/camera_undistortion_config.json"
        
        # 状态变量
        self.is_processing = False
        self.should_stop = False
        self.executor = None
        
        # 畸变参数变量
        self.hfov = tk.StringVar(value="90.0")  # 水平视场角
        self.ideal_hfov = tk.StringVar(value="90.0")  # 理想水平视场角
        self.ar = tk.StringVar(value="1.0")     # 宽高比
        self.cu = tk.StringVar(value="0.0")     # 主点x坐标
        self.cv = tk.StringVar(value="0.0")     # 主点y坐标
        self.k1 = tk.StringVar(value="0.0")     # 径向畸变系数1
        self.k2 = tk.StringVar(value="0.0")     # 径向畸变系数2
        self.k3 = tk.StringVar(value="0.0")     # 径向畸变系数3
        self.k4 = tk.StringVar(value="0.0")     # 径向畸变系数4
        self.k5 = tk.StringVar(value="0.0")     # 径向畸变系数5
        self.k6 = tk.StringVar(value="0.0")     # 径向畸变系数6
        self.p1 = tk.StringVar(value="0.0")     # 切向畸变系数1
        self.p2 = tk.StringVar(value="0.0")     # 切向畸变系数2
        
        self.create_ui()
        self.load_config()
        
    def create_ui(self):
        # 设置窗口最小大小和默认大小
        self.root.minsize(1000, 800)
        self.root.geometry("1000x800")
        
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置主窗口的网格权重
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # 创建左右分栏
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 左侧：基本设置
        self.create_basic_settings(left_frame)
        
        # 右侧：畸变参数设置
        self.create_distortion_settings(right_frame)
        
        # 配置列权重
        main_frame.grid_columnconfigure(1, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)
        
    def create_basic_settings(self, parent):
        # 输入源选择
        ttk.Label(parent, text="输入源:").grid(row=0, column=0, sticky=tk.W)
        self.input_source = tk.StringVar()
        ttk.Entry(parent, textvariable=self.input_source).grid(row=0, column=1, sticky=(tk.W, tk.E))
        ttk.Button(parent, text="选择文件", command=lambda: self.browse_input_source(True)).grid(row=0, column=2)
        ttk.Button(parent, text="选择文件夹", command=lambda: self.browse_input_source(False)).grid(row=0, column=3)
        
        # 输出目录选择
        ttk.Label(parent, text="输出目录:").grid(row=1, column=0, sticky=tk.W)
        self.output_dir = tk.StringVar()
        ttk.Entry(parent, textvariable=self.output_dir).grid(row=1, column=1, sticky=(tk.W, tk.E))
        ttk.Button(parent, text="选择文件夹", command=self.browse_output_dir).grid(row=1, column=2)
        ttk.Button(parent, text="打开目录", command=self.open_output_dir).grid(row=1, column=3)
        
        # 输出前缀
        ttk.Label(parent, text="输出前缀:").grid(row=2, column=0, sticky=tk.W)
        self.output_prefix = tk.StringVar()
        ttk.Entry(parent, textvariable=self.output_prefix).grid(row=2, column=1, sticky=(tk.W, tk.E))
        
        # 清空输出目录选项
        self.clear_output = tk.BooleanVar()
        ttk.Checkbutton(parent, text="清空输出目录", variable=self.clear_output).grid(row=3, column=0, columnspan=2, sticky=tk.W)
        
        # 多线程设置
        ttk.Label(parent, text="处理线程数:").grid(row=3, column=2, sticky=tk.E)
        self.thread_count = tk.StringVar(value="1")
        thread_entry = ttk.Entry(parent, textvariable=self.thread_count, width=5)
        thread_entry.grid(row=3, column=3, sticky=tk.W)
        
        # 进度条
        progress_frame = ttk.Frame(parent)
        progress_frame.grid(row=4, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=10)
        self.progress_var = tk.StringVar(value="准备就绪")
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(side=tk.TOP, anchor=tk.W)
        self.progress = ttk.Progressbar(progress_frame, length=300, mode='determinate')
        self.progress.pack(fill=tk.X, expand=True)
        
        # 日志输出框
        self.log_text = tk.Text(parent, height=15)
        self.log_text.grid(row=5, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=5, column=4, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        # 底部按钮
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=6, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Button(button_frame, text="退出", command=self.root.quit).pack(side=tk.LEFT, padx=5)
        self.convert_button = ttk.Button(button_frame, text="转换", command=self.toggle_conversion)
        self.convert_button.pack(side=tk.RIGHT, padx=5)
        
        # 配置列权重
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(5, weight=1)
        
    def create_distortion_settings(self, parent):
        # 创建参数输入框架
        params_frame = ttk.LabelFrame(parent, text="畸变参数设置", padding="5")
        params_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # 创建文本输入区域
        text_frame = ttk.LabelFrame(params_frame, text="参数文本输入", padding="5")
        text_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # 创建文本框和滚动条
        text_container = ttk.Frame(text_frame)
        text_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        self.param_text = tk.Text(text_container, height=6, width=50)
        self.param_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(text_container, orient=tk.VERTICAL, command=self.param_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.param_text.configure(yscrollcommand=scrollbar.set)
        
        # 添加解析按钮
        button_frame = ttk.Frame(text_frame)
        button_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Button(button_frame, text="解析参数", 
                  command=self.parse_text_parameters).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="清空", 
                  command=lambda: self.param_text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="加载XML示例", 
                  command=lambda: self.load_example(self.param_text, "xml")).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="加载JSON示例", 
                  command=lambda: self.load_example(self.param_text, "json")).pack(side=tk.LEFT, padx=5)
        
        # 配置文本框架的网格权重
        text_frame.grid_columnconfigure(0, weight=1)
        text_container.grid_columnconfigure(0, weight=1)
        text_container.grid_rowconfigure(0, weight=1)
        
        # 创建参数输入行，标记必需和可选参数
        params = [
            ("水平视场角 (hfov) *:", self.hfov, True),  # 必需参数
            ("理想水平视场角 (ideal-hfov):", self.ideal_hfov, False),  # 可选参数
            ("宽高比 (ar) *:", self.ar, True),  # 必需参数
            ("主点x坐标 (cu):", self.cu, False),  # 可选参数
            ("主点y坐标 (cv):", self.cv, False),  # 可选参数
            ("径向畸变系数1 (k1):", self.k1, False),  # 可选参数
            ("径向畸变系数2 (k2):", self.k2, False),  # 可选参数
            ("径向畸变系数3 (k3):", self.k3, False),  # 可选参数
            ("径向畸变系数4 (k4):", self.k4, False),  # 可选参数
            ("径向畸变系数5 (k5):", self.k5, False),  # 可选参数
            ("径向畸变系数6 (k6):", self.k6, False),  # 可选参数
            ("切向畸变系数1 (p1):", self.p1, False),  # 可选参数
            ("切向畸变系数2 (p2):", self.p2, False),  # 可选参数
        ]
        
        # 添加说明标签
        ttk.Label(params_frame, text="* 表示必需参数，其他参数可选，留空默认为0").grid(
            row=1, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2
        )
        
        for i, (label, var, required) in enumerate(params, start=2):
            ttk.Label(params_frame, text=label).grid(row=i, column=0, sticky=tk.W, padx=5, pady=2)
            entry = ttk.Entry(params_frame, textvariable=var, width=15)
            entry.grid(row=i, column=1, sticky=tk.W, padx=5, pady=2)
            if required:
                entry.configure(style='Required.TEntry')
        
        # 创建必需参数的样式
        style = ttk.Style()
        style.configure('Required.TEntry', foreground='blue')
        
        # 添加预设按钮框架
        preset_frame = ttk.LabelFrame(parent, text="参数预设", padding="5")
        preset_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        ttk.Button(preset_frame, text="重置参数", command=self.reset_parameters).pack(side=tk.LEFT, padx=5)
        ttk.Button(preset_frame, text="保存预设", command=self.save_preset).pack(side=tk.LEFT, padx=5)
        ttk.Button(preset_frame, text="加载预设", command=self.load_preset).pack(side=tk.LEFT, padx=5)
        
        # 配置列权重
        parent.grid_columnconfigure(0, weight=1)
        
    def reset_parameters(self):
        self.hfov.set("90.0")
        self.ideal_hfov.set("90.0")
        self.ar.set("1.0")
        self.cu.set("0.0")
        self.cv.set("0.0")
        self.k1.set("0.0")
        self.k2.set("0.0")
        self.k3.set("0.0")
        self.k4.set("0.0")
        self.k5.set("0.0")
        self.k6.set("0.0")
        self.p1.set("0.0")
        self.p2.set("0.0")
        
    def save_preset(self):
        preset_file = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            title="保存参数预设"
        )
        if preset_file:
            preset = {
                "hfov": self.hfov.get(),
                "ideal_hfov": self.ideal_hfov.get(),
                "ar": self.ar.get(),
                "cu": self.cu.get(),
                "cv": self.cv.get(),
                "k1": self.k1.get(),
                "k2": self.k2.get(),
                "k3": self.k3.get(),
                "k4": self.k4.get(),
                "k5": self.k5.get(),
                "k6": self.k6.get(),
                "p1": self.p1.get(),
                "p2": self.p2.get()
            }
            with open(preset_file, "w") as f:
                json.dump(preset, f, indent=4)
            self.log(f"参数预设已保存到: {preset_file}")
            
    def load_preset(self):
        preset_file = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            title="加载参数预设"
        )
        if preset_file:
            try:
                with open(preset_file, "r") as f:
                    preset = json.load(f)
                self.hfov.set(preset.get("hfov", "90.0"))
                self.ideal_hfov.set(preset.get("ideal_hfov", "90.0"))
                self.ar.set(preset.get("ar", "1.0"))
                self.cu.set(preset.get("cu", "0.0"))
                self.cv.set(preset.get("cv", "0.0"))
                self.k1.set(preset.get("k1", "0.0"))
                self.k2.set(preset.get("k2", "0.0"))
                self.k3.set(preset.get("k3", "0.0"))
                self.k4.set(preset.get("k4", "0.0"))
                self.k5.set(preset.get("k5", "0.0"))
                self.k6.set(preset.get("k6", "0.0"))
                self.p1.set(preset.get("p1", "0.0"))
                self.p2.set(preset.get("p2", "0.0"))
                self.log(f"已加载参数预设: {preset_file}")
            except Exception as e:
                messagebox.showerror("错误", f"加载预设失败: {str(e)}")
                
    def browse_input_source(self, is_file):
        if is_file:
            path = filedialog.askopenfilename(filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff")
            ])
        else:
            path = filedialog.askdirectory()
        if path:
            self.input_source.set(path)
            
    def browse_output_dir(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir.set(folder)
            
    def open_output_dir(self):
        output_dir = self.output_dir.get()
        if os.path.exists(output_dir):
            if os.name == 'nt':  # Windows
                os.startfile(output_dir)
            else:  # macOS 和 Linux
                import subprocess
                subprocess.run(['xdg-open' if os.name == 'posix' else 'open', output_dir])
        else:
            messagebox.showwarning("警告", "输出目录不存在")
            
    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        
    def save_config(self):
        config = {
            "input_source": self.input_source.get(),
            "output_dir": self.output_dir.get(),
            "output_prefix": self.output_prefix.get(),
            "clear_output": self.clear_output.get(),
            "thread_count": self.thread_count.get(),
            "hfov": self.hfov.get(),
            "ideal_hfov": self.ideal_hfov.get(),
            "ar": self.ar.get(),
            "cu": self.cu.get(),
            "cv": self.cv.get(),
            "k1": self.k1.get(),
            "k2": self.k2.get(),
            "k3": self.k3.get(),
            "k4": self.k4.get(),
            "k5": self.k5.get(),
            "k6": self.k6.get(),
            "p1": self.p1.get(),
            "p2": self.p2.get()
        }
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=4)
            
    def load_config(self):
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
                self.input_source.set(config.get("input_source", ""))
                self.output_dir.set(config.get("output_dir", ""))
                self.output_prefix.set(config.get("output_prefix", ""))
                self.clear_output.set(config.get("clear_output", False))
                self.thread_count.set(config.get("thread_count", "1"))
                self.hfov.set(config.get("hfov", "90.0"))
                self.ideal_hfov.set(config.get("ideal_hfov", "90.0"))
                self.ar.set(config.get("ar", "1.0"))
                self.cu.set(config.get("cu", "0.0"))
                self.cv.set(config.get("cv", "0.0"))
                self.k1.set(config.get("k1", "0.0"))
                self.k2.set(config.get("k2", "0.0"))
                self.k3.set(config.get("k3", "0.0"))
                self.k4.set(config.get("k4", "0.0"))
                self.k5.set(config.get("k5", "0.0"))
                self.k6.set(config.get("k6", "0.0"))
                self.p1.set(config.get("p1", "0.0"))
                self.p2.set(config.get("p2", "0.0"))
        except FileNotFoundError:
            pass
            
    def get_distortion_parameters(self):
        try:
            # 验证必需参数
            required_params = {
                'hfov': self.hfov.get(),
                'ar': self.ar.get()
            }
            
            for param, value in required_params.items():
                if not value.strip():
                    raise ValueError(f"必需参数 {param} 不能为空")
                try:
                    float(value)
                except ValueError:
                    raise ValueError(f"参数 {param} 必须是有效的数字")
            
            # 获取所有参数，可选参数为空时设为0
            params = {
                "hfov": float(self.hfov.get()),
                "ideal_hfov": float(self.ideal_hfov.get()) if self.ideal_hfov.get().strip() else float(self.hfov.get()),
                "ar": float(self.ar.get()),
                "cu": float(self.cu.get()) if self.cu.get().strip() else 0.0,
                "cv": float(self.cv.get()) if self.cv.get().strip() else 0.0,
                "k1": float(self.k1.get()) if self.k1.get().strip() else 0.0,
                "k2": float(self.k2.get()) if self.k2.get().strip() else 0.0,
                "k3": float(self.k3.get()) if self.k3.get().strip() else 0.0,
                "k4": float(self.k4.get()) if self.k4.get().strip() else 0.0,
                "k5": float(self.k5.get()) if self.k5.get().strip() else 0.0,
                "k6": float(self.k6.get()) if self.k6.get().strip() else 0.0,
                "p1": float(self.p1.get()) if self.p1.get().strip() else 0.0,
                "p2": float(self.p2.get()) if self.p2.get().strip() else 0.0
            }
            
            # 记录使用的参数
            used_params = {k: v for k, v in params.items() if v != 0.0 or k in ['hfov', 'ar', 'ideal_hfov']}
            self.log(f"使用的畸变参数: {used_params}")
            
            return params
            
        except ValueError as e:
            raise ValueError(str(e))
            
    def toggle_conversion(self):
        if not self.is_processing:
            # 开始转换
            if not self.input_source.get() or not os.path.exists(self.input_source.get()):
                messagebox.showerror("错误", "请选择输入源")
                return
                
            if not self.output_dir.get():
                messagebox.showerror("错误", "请指定输出目录")
                return
                
            try:
                # 验证参数
                self.get_distortion_parameters()
            except ValueError as e:
                messagebox.showerror("错误", str(e))
                return
            
            # 清空日志
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(tk.END, "开始转换...\n")
            self.progress['value'] = 0
            
            # 更新状态和按钮文字
            self.is_processing = True
            self.should_stop = False
            self.convert_button.configure(text="停止")
            
            # 启动后台线程
            thread = threading.Thread(target=self.process_images)
            thread.start()
        else:
            # 停止转换
            self.should_stop = True
            self.log_text.insert(tk.END, "正在停止转换...\n")
            self.log_text.see(tk.END)
            
    def process_images(self):
        try:
            # 记录开始时间
            start_time = time.time()
            
            # 获取线程数
            try:
                thread_count = max(1, min(32, int(self.thread_count.get())))
            except ValueError:
                thread_count = 1
                self.thread_count.set("1")

            # 获取畸变参数
            params = self.get_distortion_parameters()
            
            input_source = self.input_source.get()
            is_single_file = os.path.isfile(input_source)
            
            if is_single_file:
                # 单个文件处理
                input_dir = os.path.dirname(input_source)
                base_name = os.path.basename(input_source)
                input_files = [base_name]
            else:
                # 文件夹处理
                input_dir = input_source
                input_files = []
                for f in os.listdir(input_dir):
                    if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff')):
                        input_files.append(f)
                
                input_files = sorted(input_files)
            
            total = len(input_files)
            if total == 0:
                self.log("未找到可处理的图像文件")
                self.is_processing = False
                self.convert_button.configure(text="转换")
                return
                
            self.progress["maximum"] = total
            
            # 检查输出目录
            output_dir = self.output_dir.get()
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            # 清空输出目录
            if self.clear_output.get():
                for file in os.listdir(output_dir):
                    file_path = os.path.join(output_dir, file)
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
            
            # 创建线程池
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=thread_count)
            futures = []
            
            # 提交所有任务
            for input_file in input_files:
                if self.should_stop:
                    break
                    
                future = self.executor.submit(
                    self.process_single_image,
                    input_file,
                    input_dir,
                    output_dir,
                    params
                )
                futures.append(future)
            
            # 处理完成的任务
            processed_count = 0
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                if self.should_stop:
                    # 取消所有未完成的任务
                    for f in futures:
                        f.cancel()
                    break
                
                if future.result():
                    processed_count += 1
                
                # 更新进度
                self.progress_var.set(f"处理中: {i+1}/{total}")
                self.progress["value"] = i + 1
                self.root.update_idletasks()

        except Exception as e:
            self.log(f"发生错误: {str(e)}")
            
        finally:
            # 关闭线程池
            if self.executor:
                self.executor.shutdown(wait=False)
                self.executor = None
            
            # 计算总用时
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = elapsed_time % 60
            
            self.is_processing = False
            self.should_stop = False
            self.convert_button.configure(text="转换")
            self.progress_var.set("处理完成")
            # 输出汇总信息
            self.log(f"\n处理完成汇总:")
            self.log(f"总计处理: {total} 个文件")
            self.log(f"成功处理: {processed_count} 个文件")
            self.log(f"失败数量: {total - processed_count} 个文件")
            self.log(f"处理线程: {thread_count} 个")
            self.log(f"总计用时: {minutes}分 {seconds:.1f}秒")
            self.save_config()

    def process_single_image(self, input_file, input_dir, output_dir, params):
        try:
            # 构建完整的输入路径
            input_path = os.path.join(input_dir, input_file)
            
            # 读取图像
            self.log(f"正在读取文件: {input_path}")
            img = cv2.imread(input_path)
            if img is None:
                self.log(f"无法读取图像文件: {input_path}")
                return False
                
            # 获取图像尺寸
            height, width = img.shape[:2]
            
            # 计算相机内参矩阵
            hfov_rad = np.radians(params['hfov'])
            fx = width / (2 * np.tan(hfov_rad / 2))
            fy = fx * params['ar']
            cx = width / 2 + params['cu']
            cy = height / 2 + params['cv']
            
            camera_matrix = np.array([
                [fx, 0, cx],
                [0, fy, cy],
                [0, 0, 1]
            ], dtype=np.float32)
            
            # 构建畸变系数，只使用非零参数
            dist_coeffs = None
            use_fisheye = False
            
            # 检查是否使用鱼眼模型
            if params['k3'] != 0 or params['k4'] != 0 or params['k5'] != 0 or params['k6'] != 0:
                use_fisheye = True
                # 鱼眼模型只需要4个参数 [k1, k2, k3, k4]
                dist_coeffs = np.array([
                    params['k1'],
                    params['k2'],
                    params['k3'],
                    params['k4']
                ], dtype=np.float32)
                self.log("使用鱼眼畸变模型")
            elif params['k1'] != 0 or params['k2'] != 0 or params['p1'] != 0 or params['p2'] != 0:
                # 标准畸变模型使用5个参数 [k1, k2, p1, p2, k3]
                dist_coeffs = np.array([
                    params['k1'],
                    params['k2'],
                    params['p1'],
                    params['p2'],
                    params['k3'] if params['k3'] != 0 else 0.0
                ], dtype=np.float32)
                self.log("使用标准畸变模型")
            else:
                # 无畸变
                dist_coeffs = np.zeros(5, dtype=np.float32)
                self.log("无畸变参数，仅进行视场角调整")
            
            # 计算新的相机矩阵
            # 如果理想视场角与输入视场角不同，调整输出图像尺寸
            if abs(params['ideal_hfov'] - params['hfov']) > 0.1:
                ideal_hfov_rad = np.radians(params['ideal_hfov'])
                ideal_fx = width / (2 * np.tan(ideal_hfov_rad / 2))
                scale = ideal_fx / fx
                new_width = int(width * scale)
                new_height = int(height * scale)
                self.log(f"调整输出图像尺寸: {width}x{height} -> {new_width}x{new_height}")
            else:
                new_width = width
                new_height = height
            
            try:
                if use_fisheye:
                    # 鱼眼畸变校正
                    new_camera_matrix = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
                        camera_matrix, dist_coeffs, (width, height), np.eye(3), balance=1.0
                    )
                    undistorted = cv2.fisheye.undistortImage(
                        img, camera_matrix, dist_coeffs, None, new_camera_matrix
                    )
                    roi = (0, 0, new_width, new_height)
                else:
                    # 标准畸变校正
                    new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
                        camera_matrix, dist_coeffs, (width, height), 1, (new_width, new_height)
                    )
                    undistorted = cv2.undistort(
                        img, camera_matrix, dist_coeffs, None, new_camera_matrix
                    )
            except cv2.error as e:
                self.log(f"OpenCV处理错误: {str(e)}")
                # 如果处理失败，尝试使用备用方法
                self.log("尝试使用备用方法处理...")
                if use_fisheye:
                    # 对于鱼眼模型，尝试使用标准畸变模型
                    dist_coeffs = np.array([
                        params['k1'],
                        params['k2'],
                        params['p1'],
                        params['p2'],
                        0.0
                    ], dtype=np.float32)
                    new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
                        camera_matrix, dist_coeffs, (width, height), 1, (new_width, new_height)
                    )
                    undistorted = cv2.undistort(
                        img, camera_matrix, dist_coeffs, None, new_camera_matrix
                    )
                else:
                    # 如果标准模型也失败，尝试无畸变处理
                    self.log("使用无畸变处理...")
                    undistorted = cv2.resize(img, (new_width, new_height))
                    roi = (0, 0, new_width, new_height)
            
            # 如果尺寸发生变化，进行裁剪或填充
            if new_width != width or new_height != height:
                # 计算裁剪区域
                x, y, w, h = roi
                if w > 0 and h > 0:
                    undistorted = undistorted[y:y+h, x:x+w]
                    self.log(f"裁剪图像到: {w}x{h}")
            
            # 准备输出文件名
            output_name = os.path.splitext(os.path.basename(input_file))[0]
            if self.output_prefix.get():
                output_name = self.output_prefix.get() + output_name
            output_path = os.path.join(output_dir, output_name + '.png')
            
            # 保存图像
            self.log(f"正在保存文件: {output_path}")
            cv2.imwrite(output_path, undistorted)
            
            self.log(f"已处理: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")
            return True
            
        except Exception as e:
            self.log(f"处理 {input_file} 时出错: {str(e)}")
            return False

    def parse_text_parameters(self):
        """解析文本框中的参数"""
        try:
            text = self.param_text.get("1.0", tk.END).strip()
            if not text:
                messagebox.showwarning("警告", "请输入参数文本")
                return
                
            # 尝试解析参数
            if text.strip().startswith('<?xml'):
                params = self.parse_xml_parameters(text)
            else:
                params = self.parse_json_parameters(text)
            
            # 更新UI参数
            self.update_parameters(params)
            
        except Exception as e:
            messagebox.showerror("解析错误", f"无法解析参数: {str(e)}")

    def load_example(self, text_widget, format_type):
        if format_type == "xml":
            example = '''<?xml version="1.0" encoding="utf-8"?>
<root type="camera-intrinsics-fisheye-v1" 
    hfov="124.00" 
    ideal-hfov="215.69" 
    ar="0.999599" 
    cu="-0.011727" 
    cv="0.000051" 
    k1="0.135104" 
    k2="-0.035097" 
    k3="-0.001388" 
    k4="0.000933"/>'''
        else:  # json
            example = '''{
    "type": "camera-intrinsics-v2",
    "hfov": 77.83,
    "ar": 0.999998,
    "cu": 0.001640,
    "cv": 0.001698,
    "k1": 0.599790,
    "k2": -0.400373,
    "k3": -0.056520,
    "k4": 1.030296,
    "k5": -0.264760,
    "k6": -0.220128,
    "p1": 0.000011,
    "p2": 0.000025
}'''
        text_widget.delete("1.0", tk.END)
        text_widget.insert("1.0", example)
        
    def parse_xml_parameters(self, xml_text):
        try:
            # 移除XML声明和空白字符
            xml_text = re.sub(r'<\?xml[^>]*\?>', '', xml_text)
            xml_text = re.sub(r'\s+', ' ', xml_text).strip()
            
            # 解析XML
            root = ET.fromstring(xml_text)
            
            # 获取参数
            params = {}
            for key in ['hfov', 'ideal-hfov', 'ar', 'cu', 'cv', 
                       'k1', 'k2', 'k3', 'k4', 'k5', 'k6', 
                       'p1', 'p2']:
                value = root.get(key)
                if value is not None:
                    # 转换ideal-hfov为ideal_hfov
                    param_key = key.replace('-', '_')
                    params[param_key] = float(value)
            
            # 检查必需参数
            if 'hfov' not in params or 'ar' not in params:
                raise ValueError("缺少必需参数 hfov 或 ar")
            
            # 如果没有ideal_hfov，使用hfov的值
            if 'ideal_hfov' not in params:
                params['ideal_hfov'] = params['hfov']
            
            return params
            
        except ET.ParseError as e:
            raise ValueError(f"XML格式错误: {str(e)}")
            
    def parse_json_parameters(self, json_text):
        try:
            # 解析JSON
            params = json.loads(json_text)
            
            # 检查必需参数
            if 'hfov' not in params or 'ar' not in params:
                raise ValueError("缺少必需参数 hfov 或 ar")
            
            # 转换参数名称（如果有连字符）
            converted_params = {}
            for key, value in params.items():
                param_key = key.replace('-', '_')
                converted_params[param_key] = float(value)
            
            # 如果没有ideal_hfov，使用hfov的值
            if 'ideal_hfov' not in converted_params:
                converted_params['ideal_hfov'] = converted_params['hfov']
            
            return converted_params
            
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON格式错误: {str(e)}")
            
    def update_parameters(self, params):
        # 更新UI参数
        self.hfov.set(str(params.get('hfov', '90.0')))
        self.ideal_hfov.set(str(params.get('ideal_hfov', params.get('hfov', '90.0'))))
        self.ar.set(str(params.get('ar', '1.0')))
        self.cu.set(str(params.get('cu', '0.0')))
        self.cv.set(str(params.get('cv', '0.0')))
        self.k1.set(str(params.get('k1', '0.0')))
        self.k2.set(str(params.get('k2', '0.0')))
        self.k3.set(str(params.get('k3', '0.0')))
        self.k4.set(str(params.get('k4', '0.0')))
        self.k5.set(str(params.get('k5', '0.0')))
        self.k6.set(str(params.get('k6', '0.0')))
        self.p1.set(str(params.get('p1', '0.0')))
        self.p2.set(str(params.get('p2', '0.0')))
        
        # 记录日志
        self.log("已导入畸变参数:")
        for key, value in params.items():
            self.log(f"  {key}: {value}")

def main():
    root = tk.Tk()
    app = CameraUndistortion(root)
    root.mainloop()

if __name__ == "__main__":
    main()
