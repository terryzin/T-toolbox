import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import json
import os
import threading
from pathlib import Path
import logging
import trimesh
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import shutil
import open3d as o3d
import win32gui
import win32con
import time
import math
import psutil

class PointCloudViewer:
    def __init__(self, parent):
        self.window = tk.Toplevel(parent)
        self.window.title("点云预览器")
        self.window.geometry("1200x800")
        
        # 创建左右分栏
        self.paned_window = ttk.PanedWindow(self.window, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        
        # 左侧控制面板
        control_frame = ttk.LabelFrame(self.paned_window, text="控制面板", padding="5")
        self.paned_window.add(control_frame, weight=1)
        
        # 点大小控制
        ttk.Label(control_frame, text="点大小:").pack(anchor=tk.W)
        self.point_size = tk.DoubleVar(value=2.0)
        point_size_scale = ttk.Scale(
            control_frame, 
            from_=0.1, 
            to=10.0,
            variable=self.point_size,
            orient=tk.HORIZONTAL,
            command=self.update_point_size
        )
        point_size_scale.pack(fill=tk.X)
        
        # 背景颜色选择
        ttk.Button(
            control_frame, 
            text="选择背景颜色", 
            command=self.choose_background_color
        ).pack(pady=5, fill=tk.X)
        
        # 视角预设
        view_frame = ttk.Frame(control_frame)
        view_frame.pack(fill=tk.X, pady=5)
        ttk.Label(view_frame, text="预设视角:").pack(side=tk.LEFT)
        views = ["正视图", "侧视图", "俯视图", "等轴测图"]
        self.view_var = tk.StringVar(value=views[3])
        view_menu = ttk.OptionMenu(
            view_frame, 
            self.view_var, 
            views[3], 
            *views, 
            command=self.change_view
        )
        view_menu.pack(side=tk.LEFT, padx=5)
        
        # 操作说明
        help_frame = ttk.LabelFrame(control_frame, text="操作说明", padding="5")
        help_frame.pack(fill=tk.X, pady=5)
        help_text = """
- 左键拖动：旋转视角
- 右键拖动：平移视角
- 鼠标滚轮：缩放
- [Ctrl + C]：将视图复制到剪贴板
- [H]：返回初始视角
        """
        ttk.Label(help_frame, text=help_text, justify=tk.LEFT).pack()
        
        # 右侧预览区域
        self.preview_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(self.preview_frame, weight=3)
        
        # 创建嵌入式渲染窗口
        self.canvas = tk.Canvas(self.preview_frame)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.vis = None
        self.pcd = None
        self.background_color = [0.1, 0.1, 0.1]
        
    def load_point_cloud(self, filename):
        try:
            # 加载点云
            self.pcd = o3d.io.read_point_cloud(filename)
            if not self.pcd.has_points():
                raise Exception("点云数据为空")
            
            # 创建可视化窗口
            if self.vis is not None:
                self.vis.destroy_window()
            
            # 确保Canvas已经被正确布局
            self.window.update_idletasks()
            
            # 获取Canvas的实际大小
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            self.vis = o3d.visualization.Visualizer()
            self.vis.create_window(
                window_name="点云预览",
                width=canvas_width,
                height=canvas_height,
                visible=True
            )
            
            # 获取Open3D窗口句柄
            def callback(hwnd, extra):
                if win32gui.GetWindowText(hwnd) == "点云预览":
                    # 获取Canvas的窗口信息
                    canvas_hwnd = self.canvas.winfo_id()
                    canvas_rect = win32gui.GetWindowRect(canvas_hwnd)
                    canvas_width = canvas_rect[2] - canvas_rect[0]
                    canvas_height = canvas_rect[3] - canvas_rect[1]
                    
                    # 设置Open3D窗口为Canvas的子窗口
                    win32gui.SetParent(hwnd, canvas_hwnd)
                    
                    # 调整Open3D窗口大小以完全填充Canvas
                    win32gui.MoveWindow(
                        hwnd,
                        0, 0,
                        canvas_width,
                        canvas_height,
                        True
                    )
                    
                    # 设置无边框窗口样式
                    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                    style = style & ~(win32con.WS_POPUP | win32con.WS_CAPTION | win32con.WS_THICKFRAME | win32con.WS_BORDER)
                    style = style | win32con.WS_CHILD
                    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
                    
                    # 移除扩展窗口样式
                    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                    ex_style = ex_style & ~(win32con.WS_EX_WINDOWEDGE | win32con.WS_EX_CLIENTEDGE | win32con.WS_EX_DLGMODALFRAME)
                    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
                    
                    # 强制重绘
                    win32gui.SetWindowPos(
                        hwnd, None, 0, 0, canvas_width, canvas_height,
                        win32con.SWP_FRAMECHANGED
                    )
            
            # 等待窗口创建完成并调整大小
            self.window.after(100, lambda: win32gui.EnumWindows(callback, None))
            
            # 添加窗口大小变化的处理
            def on_resize(event):
                if event.widget == self.canvas:
                    # 重新获取Canvas大小并调整Open3D窗口
                    canvas_hwnd = self.canvas.winfo_id()
                    canvas_rect = win32gui.GetWindowRect(canvas_hwnd)
                    canvas_width = canvas_rect[2] - canvas_rect[0]
                    canvas_height = canvas_rect[3] - canvas_rect[1]
                    
                    # 查找Open3D窗口并调整大小
                    def resize_callback(hwnd, extra):
                        if win32gui.GetWindowText(hwnd) == "点云预览":
                            win32gui.MoveWindow(hwnd, 0, 0, canvas_width, canvas_height, True)
                    
                    win32gui.EnumWindows(resize_callback, None)
            
            # 绑定调整大小事件
            self.canvas.bind('<Configure>', on_resize)
            
            # 添加点云并设置渲染选项
            self.vis.add_geometry(self.pcd)
            
            render_option = self.vis.get_render_option()
            render_option.background_color = self.background_color
            render_option.point_size = float(self.point_size.get())
            render_option.show_coordinate_frame = True
            
            # 设置视图
            view_control = self.vis.get_view_control()
            view_control.set_front([0.8573, 0.4286, 0.2857])
            view_control.set_up([0, 0, 1])
            view_control.set_zoom(0.7)
            
            # 更新渲染
            self.vis.update_geometry(self.pcd)
            self.vis.poll_events()
            self.vis.update_renderer()
            
            # 创建渲染循环
            def update():
                if self.vis and self.window.winfo_exists():
                    self.vis.poll_events()
                    self.vis.update_renderer()
                    self.window.after(10, update)
                else:
                    if self.vis:
                        self.vis.destroy_window()
            
            self.window.after(10, update)
            
        except Exception as e:
            messagebox.showerror("错误", f"加载点云失败: {str(e)}")
    
    def update_point_size(self, _=None):
        if self.vis:
            render_option = self.vis.get_render_option()
            render_option.point_size = float(self.point_size.get())
    
    def choose_background_color(self):
        color = colorchooser.askcolor(
            title="选择背景颜色",
            color=self.rgb_to_hex(self.background_color)
        )
        if color[0] and self.vis:
            self.background_color = [x/255 for x in color[0]]
            render_option = self.vis.get_render_option()
            render_option.background_color = self.background_color
    
    def change_view(self, view_name):
        if not self.vis:
            return
        
        view_control = self.vis.get_view_control()
        if view_name == "正视图":
            view_control.set_front([1, 0, 0])
            view_control.set_up([0, 0, 1])
        elif view_name == "侧视图":
            view_control.set_front([0, 1, 0])
            view_control.set_up([0, 0, 1])
        elif view_name == "俯视图":
            view_control.set_front([0, 0, 1])
            view_control.set_up([0, 1, 0])
        elif view_name == "等轴测图":
            view_control.set_front([0.8573, 0.4286, 0.2857])
            view_control.set_up([0, 0, 1])
            view_control.set_zoom(0.7)
    
    @staticmethod
    def rgb_to_hex(rgb):
        return '#{:02x}{:02x}{:02x}'.format(
            int(rgb[0]*255),
            int(rgb[1]*255),
            int(rgb[2]*255)
        )

class Mesh2PointCloudGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Mesh to PointCloud Converter")
        
        # 检查必要的库
        try:
            import trimesh
            import numpy as np
            import open3d as o3d
        except ImportError as e:
            messagebox.showerror("错误", f"缺少必要的库: {str(e)}\n请使用pip安装缺失的库")
            root.destroy()
            return
        
        # 检查FBX支持
        try:
            import pymeshlab
            self.has_fbx_support = True
        except ImportError:
            self.has_fbx_support = False
            messagebox.showwarning("警告", "未安装pymeshlab库，将无法处理FBX文件\n如需处理FBX文件，请使用pip install pymeshlab安装")
        
        # 检查psutil库
        try:
            import psutil
            self.has_memory_monitor = True
        except ImportError:
            self.has_memory_monitor = False
            messagebox.showwarning("警告", "未安装psutil库，将无法监控内存使用\n建议使用pip install psutil安装")
        
        # 配置文件路径
        self.config_file = "config.json"
        self.default_config = {
            "input_path": "",
            "output_path": "",
            "prefix": "",
            "clear_output": False,
            "threads": 1,
            "output_format": "ply"
        }
        
        # 加载配置
        self.config = self.load_config()
        
        # 创建主框架
        self.create_main_frame()
        
        # 创建变量
        self.input_path = tk.StringVar(value=self.config["input_path"])
        self.output_path = tk.StringVar(value=self.config["output_path"])
        self.prefix = tk.StringVar(value=self.config["prefix"])
        self.clear_output = tk.BooleanVar(value=self.config["clear_output"])
        self.threads = tk.StringVar(value=str(self.config["threads"]))
        self.preview_path = tk.StringVar()
        self.is_converting = False
        self.stop_flag = False
        self.output_format = tk.StringVar(value=self.config.get("output_format", "ply"))
        
        # 创建UI元素
        self.create_input_frame()
        self.create_output_frame()
        self.create_options_frame()
        self.create_progress_frame()
        self.create_log_frame()
        self.create_button_frame()
        self.create_preview_frame()
        
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def create_main_frame(self):
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
    def create_input_frame(self):
        input_frame = ttk.LabelFrame(self.main_frame, text="输入源", padding="5")
        input_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Entry(input_frame, textvariable=self.input_path, width=50).grid(row=0, column=0, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(input_frame, text="选择文件", command=self.select_input_file).grid(row=0, column=1, padx=5)
        ttk.Button(input_frame, text="选择文件夹", command=self.select_input_folder).grid(row=0, column=2, padx=5)
        input_frame.columnconfigure(0, weight=1)
        
    def create_output_frame(self):
        output_frame = ttk.LabelFrame(self.main_frame, text="输出文件夹", padding="5")
        output_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Entry(output_frame, textvariable=self.output_path, width=50).grid(row=0, column=0, padx=5, sticky=(tk.W, tk.E))
        ttk.Button(output_frame, text="选择文件夹", command=self.select_output_folder).grid(row=0, column=1, padx=5)
        ttk.Button(output_frame, text="打开文件夹", command=self.open_output_folder).grid(row=0, column=2, padx=5)
        output_frame.columnconfigure(0, weight=1)
        
    def create_options_frame(self):
        options_frame = ttk.Frame(self.main_frame)
        options_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 前缀输入
        ttk.Label(options_frame, text="输出前缀:").grid(row=0, column=0, padx=5)
        ttk.Entry(options_frame, textvariable=self.prefix, width=20).grid(row=0, column=1, padx=5, sticky=tk.W)
        
        # 输出格式选择
        ttk.Label(options_frame, text="输出格式:").grid(row=0, column=2, padx=5)
        format_menu = ttk.OptionMenu(options_frame, self.output_format, "ply", "ply", "xyz")
        format_menu.grid(row=0, column=3, padx=5)
        
        # 清空输出目录选项
        ttk.Checkbutton(options_frame, text="清空输出目录", variable=self.clear_output).grid(row=0, column=4, padx=5)
        
        # 线程数输入
        ttk.Label(options_frame, text="线程数:").grid(row=0, column=5, padx=5)
        ttk.Entry(options_frame, textvariable=self.threads, width=5).grid(row=0, column=6, padx=5)
        
    def create_progress_frame(self):
        progress_frame = ttk.Frame(self.main_frame)
        progress_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.progress = ttk.Progressbar(progress_frame, length=300, mode='determinate')
        self.progress.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.progress_label = ttk.Label(progress_frame, text="0/0")
        self.progress_label.grid(row=0, column=1, padx=5)
        progress_frame.columnconfigure(0, weight=1)
        
    def create_log_frame(self):
        log_frame = ttk.LabelFrame(self.main_frame, text="日志", padding="5")
        log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, width=50)
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
    def create_button_frame(self):
        button_frame = ttk.Frame(self.main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.E), pady=5)
        
        self.convert_button = ttk.Button(button_frame, text="转换", command=self.toggle_conversion)
        self.convert_button.grid(row=0, column=0, padx=5)
        
        ttk.Button(button_frame, text="退出", command=self.on_closing).grid(row=0, column=1, padx=5)
        
    def create_preview_frame(self):
        preview_frame = ttk.LabelFrame(self.main_frame, text="点云预览", padding="5")
        preview_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 点云文件选择
        ttk.Entry(
            preview_frame, 
            textvariable=self.preview_path, 
            width=50
        ).grid(row=0, column=0, padx=5, sticky=(tk.W, tk.E))
        
        ttk.Button(
            preview_frame, 
            text="选择点云", 
            command=self.select_point_cloud
        ).grid(row=0, column=1, padx=5)
        
        ttk.Button(
            preview_frame, 
            text="预览", 
            command=self.preview_point_cloud
        ).grid(row=0, column=2, padx=5)
        
        preview_frame.columnconfigure(0, weight=1)
        
    def select_input_file(self):
        filetypes = (
            ('3D模型文', '*.obj;*.fbx'),
            ('所有文件', '*.*')
        )
        filename = filedialog.askopenfilename(filetypes=filetypes)
        if filename:
            self.input_path.set(filename)
            
    def select_input_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_path.set(folder)
            
    def select_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_path.set(folder)
            
    def open_output_folder(self):
        if os.path.exists(self.output_path.get()):
            os.startfile(self.output_path.get())
        else:
            messagebox.showwarning("告", "输出文件夹不存在！")
            
    def toggle_conversion(self):
        if not self.is_converting:
            self.start_conversion()
        else:
            self.stop_conversion()
            
    def start_conversion(self):
        if not self.validate_inputs():
            return
        
        self.stop_flag = False
        self.is_converting = True
        self.convert_button.configure(text="停止")
        
        # 开始转换线程
        self.conversion_thread = threading.Thread(target=self.convert_process)
        self.conversion_thread.start()
    
    def stop_conversion(self):
        self.stop_flag = True
        self.log_message("正在停止转换...")
        
    def convert_process(self):
        try:
            input_path = self.input_path.get()
            output_path = self.output_path.get()
            prefix = self.prefix.get()
            thread_count = int(self.threads.get())
            
            self.log_message("=== 开始转换任务 ===")
            self.log_message(f"输入路径: {input_path}")
            self.log_message(f"输出路径: {output_path}")
            self.log_message(f"输出前缀: {prefix}")
            self.log_message(f"线程数: {thread_count}")
            self.log_message(f"输出格式: {self.output_format.get()}")
            
            # 确保输出目录存在
            os.makedirs(output_path, exist_ok=True)
            
            # 如果选择清空输出目录
            if self.clear_output.get():
                self.log_message("\n正在清空输出目录...")
                cleared_files = 0
                for item in os.listdir(output_path):
                    item_path = os.path.join(output_path, item)
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                        cleared_files += 1
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        cleared_files += 1
                self.log_message(f"已清空输出目录，移除了 {cleared_files} 个项目")
            
            # 获取需要处理的文件列表
            self.log_message("\n正在扫描文件...")
            files_to_process = []
            total_size = 0
            if os.path.isfile(input_path):
                size = os.path.getsize(input_path)
                files_to_process.append((input_path, size))
                total_size += size
            else:
                for root, _, files in os.walk(input_path):
                    for file in files:
                        if file.lower().endswith(('.obj', '.fbx')):
                            file_path = os.path.join(root, file)
                            size = os.path.getsize(file_path)
                            files_to_process.append((file_path, size))
                            total_size += size
            
            total_files = len(files_to_process)
            if total_files == 0:
                self.log_message("没有找到可处理的文件")
                return
            
            self.log_message(f"找到 {total_files} 个文件，总大小: {self.format_size(total_size)}")
            self.update_progress(0, total_files)
            
            # 按文件大小排序，从大到小处理
            files_to_process.sort(key=lambda x: x[1], reverse=True)
            
            completed_count = 0
            successful_count = 0
            failed_count = 0
            total_processed_size = 0
            
            # 使用线程池处理文件
            self.log_message("\n开始处理文件...")
            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                futures = []
                for file_path, size in files_to_process:
                    if self.stop_flag:
                        break
                    future = executor.submit(self.convert_single_file, file_path, output_path, prefix)
                    futures.append((future, size))
                
                # 处理结果
                for future, size in futures:
                    if self.stop_flag:
                        break
                    success, message = future.result()
                    self.log_message(message)
                    completed_count += 1
                    total_processed_size += size
                    if success:
                        successful_count += 1
                    else:
                        failed_count += 1
                    self.update_progress(completed_count, total_files)
            
            # 输出汇总信息
            self.log_message("\n=== 转换任务完成 ===")
            if self.stop_flag:
                self.log_message("转换已被用户停止")
            self.log_message(f"处理完成: {completed_count}/{total_files} 个文件")
            self.log_message(f"成功: {successful_count} 个")
            self.log_message(f"失败: {failed_count} 个")
            self.log_message(f"总处理大小: {self.format_size(total_processed_size)}")
            
        except Exception as e:
            self.log_message(f"\n转换过程出错: {str(e)}")
            import traceback
            self.log_message(traceback.format_exc())
        finally:
            self.stop_flag = False
            self.is_converting = False
            self.convert_button.configure(text="转换")
    
    def convert_single_file(self, input_file, output_dir, prefix=""):
        try:
            file_size = os.path.getsize(input_file)
            self.log_message(f"\n处理文件: {input_file}")
            self.log_message(f"文件大小: {self.format_size(file_size)}")
            
            # 估算内存使用
            estimated_memory = self.estimate_memory_usage(file_size)
            available_memory = self.get_available_memory()
            self.log_message(f"预计内存使用: {self.format_size(estimated_memory)}")
            self.log_message(f"可用系统内存: {self.format_size(available_memory)}")
            
            if estimated_memory > available_memory * 0.8:  # 如果预计使用超过80%的可用内存
                self.log_message("警告: 文件较大，将使用分块处理以减少内存占用")
                return self.convert_large_file(input_file, output_dir, prefix)
            
            start_time = time.time()
            
            # 获取文件扩展名
            file_ext = os.path.splitext(input_file)[1].lower()
            
            # 加载模型
            self.log_message("正在加载模型...")
            if file_ext == '.fbx':
                try:
                    import pymeshlab
                    ms = pymeshlab.MeshSet()
                    ms.load_new_mesh(input_file)
                    self.log_message("正在转换FBX到临时OBJ...")
                    temp_obj = os.path.join(output_dir, "_temp.obj")
                    ms.save_current_mesh(temp_obj)
                    self.log_message("正在加载转换后的模型...")
                    mesh = trimesh.load(temp_obj)
                    os.remove(temp_obj)
                except ImportError:
                    return False, "处理FBX文件需要安装pymeshlab库，请使用pip install pymeshlab安装"
            else:
                mesh = trimesh.load(input_file)
            
            load_time = time.time() - start_time
            self.log_message(f"模型加载耗时: {load_time:.2f}秒")
            
            # 获取顶点和颜色信息
            vertices = mesh.vertices
            vertex_count = len(vertices)
            self.log_message(f"模型顶点数: {vertex_count:,}")
            
            # 获取颜色信息
            if hasattr(mesh.visual, 'vertex_colors'):
                colors = mesh.visual.vertex_colors
                self.log_message("已获取顶点颜色信息")
            else:
                colors = np.ones((vertex_count, 4), dtype=np.uint8) * 255
                self.log_message("未找到顶点颜色，使用默认白色")
            
            # 清理不需要的数据以释放内存
            del mesh
            
            # 创建输出文件
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            output_format = self.output_format.get()
            output_file = os.path.join(output_dir, f"{prefix}{base_name}.{output_format}")
            
            self.log_message(f"正在导出为{output_format.upper()}格式...")
            export_start = time.time()
            
            if output_format == "ply":
                cloud = trimesh.PointCloud(vertices=vertices, colors=colors)
                cloud.export(output_file)
            elif output_format == "xyz":
                np.savetxt(output_file, vertices, fmt='%.6f')
            
            export_time = time.time() - export_start
            total_time = time.time() - start_time
            
            output_size = os.path.getsize(output_file)
            self.log_message(f"输出文件大小: {self.format_size(output_size)}")
            self.log_message(f"导出耗时: {export_time:.2f}秒")
            self.log_message(f"总处理时间: {total_time:.2f}秒")
            
            return True, f"成功转换 {input_file} -> {output_file}"
        except Exception as e:
            error_msg = f"转换失败 {input_file}: {str(e)}"
            import traceback
            self.log_message(traceback.format_exc())
            return False, error_msg
    
    def convert_large_file(self, input_file, output_dir, prefix=""):
        """分块处理大型文件"""
        try:
            start_time = time.time()
            self.log_message("开始分块处理大型文件...")
            
            # 使用内存映射加载文件
            mesh = trimesh.load(input_file, process=False)
            total_vertices = len(mesh.vertices)
            
            # 计算每块的大小（约100MB内存使用）
            chunk_size = min(1000000, total_vertices)  # 每块最多100万个顶点
            chunks = math.ceil(total_vertices / chunk_size)
            self.log_message(f"将分{chunks}块处理，每块{chunk_size:,}个顶点")
            
            # 准备输出文件
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            output_format = self.output_format.get()
            output_file = os.path.join(output_dir, f"{prefix}{base_name}.{output_format}")
            
            if output_format == "ply":
                # 创建PLY文件头
                with open(output_file, 'wb') as f:
                    header = (
                        f"ply\n"
                        f"format binary_little_endian 1.0\n"
                        f"element vertex {total_vertices}\n"
                        f"property float x\n"
                        f"property float y\n"
                        f"property float z\n"
                        f"property uchar red\n"
                        f"property uchar green\n"
                        f"property uchar blue\n"
                        f"property uchar alpha\n"
                        f"end_header\n"
                    ).encode()
                    f.write(header)
            
            # 分块处理
            processed_vertices = 0
            for i in range(chunks):
                chunk_start = i * chunk_size
                chunk_end = min((i + 1) * chunk_size, total_vertices)
                self.log_message(f"正在处理第{i+1}/{chunks}块...")
                
                # 获取当前块的顶点
                vertices_chunk = mesh.vertices[chunk_start:chunk_end]
                
                # 获取颜色信息
                if hasattr(mesh.visual, 'vertex_colors'):
                    colors_chunk = mesh.visual.vertex_colors[chunk_start:chunk_end]
                else:
                    colors_chunk = np.ones((len(vertices_chunk), 4), dtype=np.uint8) * 255
                
                # 写入数据
                if output_format == "ply":
                    with open(output_file, 'ab') as f:
                        vertex_data = np.hstack((
                            vertices_chunk.astype(np.float32),
                            colors_chunk.astype(np.uint8)
                        ))
                        vertex_data.tofile(f)
                elif output_format == "xyz":
                    with open(output_file, 'a' if i > 0 else 'w') as f:
                        np.savetxt(f, vertices_chunk, fmt='%.6f')
                
                processed_vertices += len(vertices_chunk)
                progress = processed_vertices / total_vertices * 100
                self.log_message(f"进度: {progress:.1f}% ({processed_vertices:,}/{total_vertices:,})")
            
            total_time = time.time() - start_time
            output_size = os.path.getsize(output_file)
            self.log_message(f"分块处理完成")
            self.log_message(f"输出文件大小: {self.format_size(output_size)}")
            self.log_message(f"总处理时间: {total_time:.2f}秒")
            
            return True, f"成功转换 {input_file} -> {output_file}"
        except Exception as e:
            error_msg = f"转换失败 {input_file}: {str(e)}"
            import traceback
            self.log_message(traceback.format_exc())
            return False, error_msg
    
    def estimate_memory_usage(self, file_size):
        """估算处理文件需要的内存"""
        # 根据经验估算：文件大小的约10倍
        return file_size * 10
    
    def get_available_memory(self):
        """获取系统可用内存"""
        try:
            return psutil.virtual_memory().available
        except ImportError:
            # 如果无法获取系统内存信息，返回一个保守的估计值（4GB）
            return 4 * 1024 * 1024 * 1024
    
    def format_size(self, size):
        """格式化文件大小显示"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
    
    def validate_inputs(self):
        if not self.input_path.get():
            messagebox.showerror("错误", "请选择输入源！")
            return False
        if not self.output_path.get():
            messagebox.showerror("错误", "请选择输出文件夹！")
            return False
        try:
            threads = int(self.threads.get())
            if threads < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "线程数必须是大于0的整数！")
            return False
        return True
        
    def update_progress(self, current, total):
        self.progress["value"] = (current / total) * 100
        self.progress_label["text"] = f"{current}/{total}"
        
    def log_message(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        
    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
        return self.default_config
        
    def save_config(self):
        config = {
            "input_path": self.input_path.get(),
            "output_path": self.output_path.get(),
            "prefix": self.prefix.get(),
            "clear_output": self.clear_output.get(),
            "threads": int(self.threads.get()),
            "output_format": self.output_format.get()
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            
    def on_closing(self):
        if self.is_converting:
            if messagebox.askokcancel("确认", "转换正在进行中，确定要退出吗？"):
                self.stop_conversion()
                self.save_config()
                self.root.destroy()
        else:
            self.save_config()
            self.root.destroy()
    
    def select_point_cloud(self):
        filetypes = (
            ('点云文件', '*.ply'),
            ('所有文件', '*.*')
        )
        filename = filedialog.askopenfilename(filetypes=filetypes)
        if filename:
            self.preview_path.set(filename)
    
    def preview_point_cloud(self):
        if not self.preview_path.get():
            messagebox.showwarning("警告", "请先选择点云文件！")
            return
            
        if not os.path.exists(self.preview_path.get()):
            messagebox.showerror("错误", "所选文件不存在！")
            return
            
        viewer = PointCloudViewer(self.root)
        viewer.load_point_cloud(self.preview_path.get())

def main():
    root = tk.Tk()
    app = Mesh2PointCloudGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 