import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import threading
import os
import csv
from PIL import Image
import time
import json
from PIL.ExifTags import TAGS, GPSTAGS
import piexif  # 添加这个导入来获取更多EXIF信息
import tkinter.scrolledtext as scrolledtext

# 在文件开头添加版本号常量
VERSION = "1.0.0"

class ColumnSelectorDialog:
    def __init__(self, parent, columns_config):
        self.top = tk.Toplevel(parent)
        self.top.title("Select Output Columns")
        self.top.geometry("500x600")
        self.result = None
        
        # 深拷贝配置，避免直接修改原配置
        self.columns_config = dict(columns_config)
        
        self.setup_gui()
        
        # 使对话框模态
        self.top.transient(parent)
        self.top.grab_set()
        
    def setup_gui(self):
        # 创建主框架
        main_frame = ttk.Frame(self.top, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建滚动区域
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 添加全选/取消全选按钮
        select_frame = ttk.Frame(scrollable_frame)
        select_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(
            select_frame,
            text="Select All",
            command=lambda: self.select_all(True)
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            select_frame,
            text="Deselect All",
            command=lambda: self.select_all(False)
        ).pack(side=tk.LEFT)
        
        # 添加分隔线
        ttk.Separator(scrollable_frame, orient='horizontal').pack(fill=tk.X, pady=5)
        
        # 创建复选框
        self.checkbuttons = {}
        for category, columns in self.columns_config.items():
            # 添加分类标签
            ttk.Label(
                scrollable_frame,
                text=category,
                font=('Microsoft YaHei', 10, 'bold')
            ).pack(anchor="w", pady=(10, 5))
            
            # 添加该分类下的复选框
            for col, selected in columns.items():
                var = tk.BooleanVar(value=selected)
                cb = ttk.Checkbutton(
                    scrollable_frame,
                    text=col,
                    variable=var
                )
                cb.pack(anchor="w", padx=20)
                self.checkbuttons[col] = var
            
            # 在每个分类后添加分隔线（最后一个分类除外）
            if category != list(self.columns_config.keys())[-1]:
                ttk.Separator(scrollable_frame, orient='horizontal').pack(fill=tk.X, pady=5)
        
        # 打包滚动组件
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            button_frame,
            text="OK",
            command=self.on_ok
        ).pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.on_cancel
        ).pack(side=tk.RIGHT)
        
        # 绑定鼠标滚轮事件
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
    
    def select_all(self, value):
        """全选或取消全选所有列"""
        for var in self.checkbuttons.values():
            var.set(value)
    
    def on_ok(self):
        """确认选择"""
        result = {}
        # 重构结果以匹配原始配置结构
        for category, columns in self.columns_config.items():
            result[category] = {
                col: self.checkbuttons[col].get() 
                for col in columns.keys()
            }
        self.result = result
        self.top.destroy()
    
    def on_cancel(self):
        """取消选择"""
        self.top.destroy()

class ImageDetailExtractor:
    def __init__(self, master):
        self.master = master
        self.output_dir = tk.StringVar()  # 确保这个变量被创建
        
        # 获取程序所在目录
        self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.app_dir, "config.json")
        
        # 设置窗口图标（如果有的话）
        try:
            self.master.iconbitmap('path/to/your/icon.ico')
        except:
            pass
        
        # 设置窗口最小尺寸
        self.master.minsize(600, 400)
        
        # 初始化界面
        self.setup_gui()
        self.is_extracting = False
        self.load_config()
        self.setup_auto_save()
        
        # 添加列配置
        self.columns_config = {
            "Basic Info": {
                "Filename": True,
                "FilePath": True,
                "Format": True,
                "Dimensions": True,
                "ColorMode": True,
                "FileSize(KB)": True,
                "BitsPerPixel": True,
                "ColorDepth": True,
                "Created": True,
                "Modified": True
            },
            "Camera Info": {
                "Make": True,
                "Model": True,
                "FNumber": True,
                "ExposureTime": True,
                "ISOSpeedRatings": True,
                "FocalLength": True,
                "MaxApertureValue": True,
                "MeteringMode": True,
                "Flash": True,
                "LensMake": True,
                "LensModel": True,
                "DateTimeOriginal": True,
                "ExposureBiasValue": True,
                "WhiteBalance": True,
                "ExposureProgram": True
            },
            "GPS Info": {
                "GPS_Longitude": True,
                "GPS_Latitude": True,
                "GPS_Altitude": True,
                "GPS_DateStamp": True,
                "GPS_TimeStamp": True,
                "GPS_ProcessingMethod": True
            }
        }

    def setup_auto_save(self):
        """设置自动保存配置的触发器"""
        # 监听输入框变化
        self.input_entry.bind('<FocusOut>', lambda e: self.save_config())
        self.output_entry.bind('<FocusOut>', lambda e: self.save_config())
        self.filename_entry.bind('<FocusOut>', lambda e: self.save_config())

    def setup_gui(self):
        # 设置窗口样式
        self.master.configure(bg='#f0f0f0')
        self.master.geometry('800x600')
        
        # 创建主容器
        main_container = ttk.Frame(self.master, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)

        # 样式配置
        style = ttk.Style()
        style.configure('Title.TLabel', font=('Microsoft YaHei', 12, 'bold'))
        style.configure('Header.TLabel', font=('Microsoft YaHei', 10, 'bold'))
        style.configure('Custom.TButton', padding=5, font=('Microsoft YaHei', 9))
        style.configure('Action.TButton', padding=10, font=('Microsoft YaHei', 10, 'bold'))
        
        # 标题
        title_frame = ttk.Frame(main_container)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(
            title_frame, 
            text=f"图像信息提取工具 v{VERSION}", 
            style='Title.TLabel'
        ).pack()

        # 输入源选择框架
        input_frame = ttk.LabelFrame(main_container, text="输入源", padding="5")
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 输入路径行
        path_frame = ttk.Frame(input_frame)
        path_frame.pack(fill=tk.X, pady=5)
        self.input_entry = ttk.Entry(path_frame)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # 按钮框架
        btn_frame = ttk.Frame(path_frame)
        btn_frame.pack(side=tk.LEFT)
        ttk.Button(
            btn_frame, 
            text="选择文件", 
            command=self.browse_file,
            style='Custom.TButton'
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            btn_frame, 
            text="选择文件夹", 
            command=self.browse_directory,
            style='Custom.TButton'
        ).pack(side=tk.LEFT, padx=2)

        # 输出设置框架
        output_frame = ttk.LabelFrame(main_container, text="输出设置", padding="5")
        output_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 出目录行
        output_dir_frame = ttk.Frame(output_frame)
        output_dir_frame.pack(fill=tk.X, pady=5)
        ttk.Label(output_dir_frame, text="输出目录:").pack(side=tk.LEFT)
        self.output_entry = ttk.Entry(output_dir_frame, textvariable=self.output_dir)
        self.output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(
            output_dir_frame, 
            text="浏览", 
            command=self.select_output_directory,
            style='Custom.TButton'
        ).pack(side=tk.LEFT)
        
        # 输出文件名行
        filename_frame = ttk.Frame(output_frame)
        filename_frame.pack(fill=tk.X, pady=5)
        ttk.Label(filename_frame, text="输出文件名:").pack(side=tk.LEFT)
        self.filename_var = tk.StringVar(value="image-details.csv")
        self.filename_entry = ttk.Entry(filename_frame, textvariable=self.filename_var)
        self.filename_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # 日志框架
        log_frame = ttk.LabelFrame(main_container, text="处理日志", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 日志文本框
        self.log_text = tk.Text(
            log_frame, 
            height=10, 
            wrap=tk.WORD,
            font=('Microsoft YaHei', 9)
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        # 进度条
        progress_frame = ttk.Frame(main_container)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        self.progress = ttk.Progressbar(
            progress_frame, 
            orient="horizontal", 
            length=100, 
            mode="determinate"
        )
        self.progress.pack(fill=tk.X)

        # 控制按钮框架
        control_frame = ttk.Frame(main_container)
        control_frame.pack(fill=tk.X)
        
        ttk.Button(
            control_frame, 
            text="退出", 
            command=self.on_closing,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)
        
        self.start_button = ttk.Button(
            control_frame, 
            text="开始提取", 
            command=self.toggle_extraction,
            style='Action.TButton'
        )
        self.start_button.pack(side=tk.RIGHT)

        # 在输出设置框架中添加列选择按钮
        columns_button = ttk.Button(
            output_frame,
            text="选择输出信息",
            command=self.show_column_selector,
            style='Custom.TButton'
        )
        columns_button.pack(pady=5)

    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=[
                ("图片文件", "*.jpg *.jpeg *.png *.tiff *.bmp"),
                ("所有文件", "*.*")
            ]
        )
        if filename:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, filename)

    def browse_directory(self):
        directory = filedialog.askdirectory(title="选择图片文件夹")
        if directory:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, directory)

    def select_output_directory(self):
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.output_dir.set(directory)

    def toggle_extraction(self):
        if not self.is_extracting:
            input_path = self.input_entry.get()
            if not input_path:
                messagebox.showerror("错误", "请选择输入文件文件夹")
                return
            
            output_dir = self.output_dir.get()
            if not output_dir:
                messagebox.showerror("错误", "请选择输出目录")
                return

            self.is_extracting = True
            self.start_button.config(text="停止提取")
            self.extract_details()
        else:
            self.is_extracting = False
            self.start_button.config(text="开始提取")

    def _convert_to_degrees(self, value):
        """Convert GPS coordinates to degrees format"""
        try:
            d = float(value[0][0]) / float(value[0][1])
            m = float(value[1][0]) / float(value[1][1])
            s = float(value[2][0]) / float(value[2][1])
            return d + (m / 60.0) + (s / 3600.0)
        except:
            return None

    def _get_gps_data(self, exif_dict):
        """Extract GPS information from EXIF data"""
        if not exif_dict or 'GPS' not in exif_dict:
            return {}

        gps = exif_dict['GPS']
        gps_info = {}

        try:
            # 提取纬度
            if 1 in gps and 2 in gps:  # GPSLatitude & GPSLatitudeRef
                lat_value = self._convert_to_degrees(gps[2])
                if lat_value is not None:
                    if gps[1] == b'S':  # South is negative
                        lat_value = -lat_value
                    gps_info['GPS_Latitude'] = f"{lat_value:.8f}"

            # 提取经度
            if 3 in gps and 4 in gps:  # GPSLongitude & GPSLongitudeRef
                lon_value = self._convert_to_degrees(gps[4])
                if lon_value is not None:
                    if gps[3] == b'W':  # West is negative
                        lon_value = -lon_value
                    gps_info['GPS_Longitude'] = f"{lon_value:.8f}"

            # 提取海拔
            if 6 in gps:  # GPSAltitude
                alt = gps[6]
                if isinstance(alt, tuple):
                    gps_info['GPS_Altitude'] = f"{float(alt[0])/float(alt[1]):.1f}"
                else:
                    gps_info['GPS_Altitude'] = str(alt)

            # 提取GPS时间戳
            if 7 in gps:  # GPSTimeStamp
                time_stamp = gps[7]
                if isinstance(time_stamp, tuple) and len(time_stamp) == 3:
                    hour = time_stamp[0][0] / time_stamp[0][1]
                    minute = time_stamp[1][0] / time_stamp[1][1]
                    second = time_stamp[2][0] / time_stamp[2][1]
                    gps_info['GPS_TimeStamp'] = f"{int(hour):02d}:{int(minute):02d}:{int(second):02d}"

            # 提取GPS日期
            if 29 in gps:  # GPSDateStamp
                date_stamp = gps[29]
                if isinstance(date_stamp, bytes):
                    gps_info['GPS_DateStamp'] = date_stamp.decode('ascii').strip()

        except Exception as e:
            print(f"GPS data extraction error: {str(e)}")

        return gps_info

    def get_selected_headers(self):
        """根据用户选择获取表头"""
        selected_headers = []
        
        # 遍历所有分类的列配置
        for category in self.columns_config:
            for header, is_selected in self.columns_config[category].items():
                if is_selected:
                    selected_headers.append(header)
        
        return selected_headers

    def extract_details(self):
        try:
            input_path = self.input_entry.get()
            output_dir = self.output_dir.get()
            filename = self.filename_var.get()
            
            # 检查输出目录是否存在
            if not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir)
                except Exception as e:
                    messagebox.showerror("错误", f"创建输出目录失败：\n{str(e)}")
                    return

            # 构建输出文件路径
            output_file = os.path.join(output_dir, filename)
            
            # 检查输入路径
            if os.path.isfile(input_path):
                if not any(input_path.lower().endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.tiff', '.bmp')):
                    messagebox.showerror("错误", "选择的文件不是支持的图片格式")
                    return
                image_files = [input_path]
            elif os.path.isdir(input_path):
                image_files = []
                for root, _, files in os.walk(input_path):
                    for file in files:
                        if file.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.bmp')):
                            image_files.append(os.path.join(root, file))
                if not image_files:
                    messagebox.showerror("错误", "所选文件夹中没有找到支持的图片文件")
                    return
            else:
                messagebox.showerror("错误", "所选路径无效")
                return

            # 检查是否可以创建输出文件
            try:
                with open(output_file, 'w', newline='', encoding='utf-8-sig') as test_file:
                    pass
            except Exception as e:
                messagebox.showerror("错误", f"无法创建输出文件：\n{str(e)}")
                return

            # 获取用户选择的表头
            selected_headers = self.get_selected_headers()
            if not selected_headers:
                messagebox.showerror("错误", "请至少选择一个输出列")
                return

            with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
                try:
                    writer = csv.writer(csvfile)
                    writer.writerow(selected_headers)  # 只写入选中的表头

                    processed_count = 0
                    start_time = time.time()
                    self.progress['maximum'] = len(image_files)

                    for image_path in image_files:
                        if not self.is_extracting:
                            break

                        try:
                            # 收集所有可能的数据
                            all_data = {}
                            
                            # 基本信息
                            img = Image.open(image_path)
                            file_stats = os.stat(image_path)
                            file_size = file_stats.st_size / 1024

                            basic_info = {
                                'Filename': os.path.basename(image_path),
                                'FilePath': image_path,
                                'Format': img.format,
                                'Dimensions': f"{img.width}x{img.height}",
                                'ColorMode': img.mode,
                                'FileSize(KB)': f"{file_size:.2f}",
                                'BitsPerPixel': str(img.bits) if hasattr(img, 'bits') else '',
                                'ColorDepth': str(getattr(img, 'depth', '')),
                                'Created': time.ctime(file_stats.st_ctime),
                                'Modified': time.ctime(file_stats.st_mtime)
                            }
                            all_data.update(basic_info)

                            # EXIF和GPS信息
                            try:
                                exif_dict = piexif.load(image_path)
                                # 处理EXIF信息
                                for ifd in ('0th', 'Exif'):
                                    if ifd in exif_dict and exif_dict[ifd]:
                                        for tag, value in exif_dict[ifd].items():
                                            tag_name = TAGS.get(tag, str(tag))
                                            if tag_name in selected_headers:
                                                if isinstance(value, bytes):
                                                    try:
                                                        value = value.decode('utf-8').strip('\x00')
                                                    except:
                                                        value = str(value)[2:-1]
                                                elif isinstance(value, tuple):
                                                    if len(value) == 2:
                                                        try:
                                                            value = f"{float(value[0]) / float(value[1]):.2f}"
                                                        except:
                                                            value = str(value)
                                                all_data[tag_name] = value

                                # 处理GPS信息
                                gps_data = self._get_gps_data(exif_dict)
                                all_data.update(gps_data)

                            except Exception as e:
                                self.log_text.insert(tk.END, f"EXIF提取错误 {image_path}: {str(e)}\n")

                            # 只输出选中的列
                            row_data = [all_data.get(header, '') for header in selected_headers]
                            writer.writerow(row_data)

                            self.log_text.insert(tk.END, f"已处理: {os.path.basename(image_path)}\n")
                            self.log_text.see(tk.END)

                        except Exception as e:
                            error_msg = f"处理文件失败 {image_path}: {str(e)}"
                            self.log_text.insert(tk.END, f"{error_msg}\n")
                            messagebox.showwarning("警告", error_msg)
                            continue

                        processed_count += 1
                        self.progress['value'] = processed_count

                    if processed_count == 0:
                        messagebox.showwarning("警告", "没有成功处理任何文件")
                    else:
                        elapsed_time = time.time() - start_time
                        success_msg = (
                            f"处理完成\n"
                            f"总文件数: {len(image_files)}\n"
                            f"成功处理: {processed_count}\n"
                            f"耗时: {elapsed_time:.2f} 秒\n"
                            f"输出文件: {output_file}"
                        )
                        self.log_text.insert(tk.END, f"\n{success_msg}\n")
                        messagebox.showinfo("完成", success_msg)

                except Exception as e:
                    error_msg = f"写入CSV文件时出错：\n{str(e)}"
                    self.log_text.insert(tk.END, f"{error_msg}\n")
                    messagebox.showerror("错误", error_msg)

        except Exception as e:
            error_msg = f"发生未知错误：\n{str(e)}"
            self.log_text.insert(tk.END, f"{error_msg}\n")
            messagebox.showerror("错误", error_msg)
        
        finally:
            self.is_extracting = False
            self.start_button.config(text="开始提取")

    def load_config(self):
        """加载配置，添加列选择配置的加载"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding='utf-8') as f:
                    config = json.load(f)
                    self.output_dir.set(config.get("output_dir", ""))
                    last_input = config.get("last_input", "")
                    if last_input:
                        self.input_entry.delete(0, tk.END)
                        self.input_entry.insert(0, last_input)
                    filename = config.get("filename", "image-details.csv")
                    self.filename_var.set(filename)
                    
                    # 加载列择配置
                    if "columns_config" in config:
                        self.columns_config = config["columns_config"]
            except Exception as e:
                self.log_text.insert(tk.END, f"Failed to load config: {str(e)}\n")

    def save_config(self):
        """保存配置"""
        config = {
            "output_dir": self.output_dir.get(),
            "last_input": self.input_entry.get(),
            "filename": self.filename_var.get(),
            "version": VERSION,
            "columns_config": self.columns_config,  # 包含列选择配置
            "columns_state": {
                column: var.get() 
                for column, var in getattr(self, 'column_vars', {}).items()
            }
        }
        try:
            # 确保置目录存在
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with open(self.config_path, "w", encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.log_text.insert(tk.END, f"Failed to save config: {str(e)}\n")
            self.log_text.see(tk.END)

    def on_closing(self):
        if self.is_extracting:
            if messagebox.askokcancel("确认", "正在提取中，确定要退出吗？"):
                self.is_extracting = False
                self.save_config()
                self.master.destroy()
        else:
            self.save_config()
            self.master.destroy()

    def show_column_selector(self):
        """显示列选择对话框"""
        selector_window = tk.Toplevel(self.master)
        selector_window.title("选择输出内容")
        selector_window.geometry("600x400")
        
        # 创建主框架
        main_frame = ttk.Frame(selector_window)
        main_frame.pack(expand=True, fill='both', padx=10, pady=10)
        
        # 创建左右列表框架
        lists_frame = ttk.Frame(main_frame)
        lists_frame.pack(expand=True, fill='both')
        
        # 左侧框架（已选择项目）
        left_frame = ttk.LabelFrame(lists_frame, text="已选择项目")
        left_frame.pack(side='left', expand=True, fill='both', padx=5)
        
        self.selected_listbox = tk.Listbox(left_frame, selectmode=tk.SINGLE)
        self.selected_listbox.pack(side='left', expand=True, fill='both')
        left_scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.selected_listbox.yview)
        left_scrollbar.pack(side='right', fill='y')
        self.selected_listbox.config(yscrollcommand=left_scrollbar.set)
        
        # 中间按钮框架
        middle_frame = ttk.Frame(lists_frame)
        middle_frame.pack(side='left', padx=10)
        
        ttk.Button(middle_frame, text="→", command=lambda: self.move_item('right')).pack(pady=5)
        ttk.Button(middle_frame, text="←", command=lambda: self.move_item('left')).pack(pady=5)
        
        # 右侧框架（可选择项目）
        right_frame = ttk.LabelFrame(lists_frame, text="可选择项目")
        right_frame.pack(side='right', expand=True, fill='both', padx=5)
        
        self.available_listbox = tk.Listbox(right_frame, selectmode=tk.SINGLE)
        self.available_listbox.pack(side='left', expand=True, fill='both')
        right_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=self.available_listbox.yview)
        right_scrollbar.pack(side='right', fill='y')
        self.available_listbox.config(yscrollcommand=right_scrollbar.set)
        
        # 排序按钮框架
        sort_frame = ttk.Frame(main_frame)
        sort_frame.pack(fill='x', pady=5)
        
        ttk.Button(sort_frame, text="上移", command=lambda: self.move_item_updown('up')).pack(side='left', padx=5)
        ttk.Button(sort_frame, text="下移", command=lambda: self.move_item_updown('down')).pack(side='left', padx=5)
        
        # 确定取消按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=10)
        
        ttk.Button(button_frame, text="确定", command=lambda: self.save_column_selection(selector_window)).pack(side='right', padx=5)
        ttk.Button(button_frame, text="取消", command=selector_window.destroy).pack(side='right', padx=5)
        
        # 初始化列表内容
        self.initialize_listboxes()
        
    def initialize_listboxes(self):
        """初始化左右列表的内容"""
        # 清空列表
        self.selected_listbox.delete(0, tk.END)
        self.available_listbox.delete(0, tk.END)
        
        # 定义所有可用的列
        self.all_possible_columns = [
            # Basic Info
            "Filename", "FilePath", "Format", "Dimensions", "ColorMode",
            "FileSize(KB)", "BitsPerPixel", "ColorDepth", "Created", "Modified",
            
            # Camera Info
            "Make", "Model", "FNumber", "ExposureTime", "ISOSpeedRatings",
            "FocalLength", "MaxApertureValue", "MeteringMode", "Flash",
            "LensMake", "LensModel", "DateTimeOriginal", "ExposureBiasValue",
            "WhiteBalance", "ExposureProgram",
            
            # GPS Info
            "GPS_Longitude", "GPS_Latitude", "GPS_Altitude",
            "GPS_DateStamp", "GPS_TimeStamp", "GPS_ProcessingMethod"
        ]
        
        # 从配置文件加载已保存的选择
        selected_columns = self.load_selected_columns()
        
        # 如果没有已保存的选择，则所有列都放在可选择列表中
        if not selected_columns:
            for col in self.all_possible_columns:
                self.available_listbox.insert(tk.END, col)
        else:
            # 填充已选择列表
            for col in selected_columns:
                self.selected_listbox.insert(tk.END, col)
            # 填充可选择列表
            for col in self.all_possible_columns:
                if col not in selected_columns:
                    self.available_listbox.insert(tk.END, col)

    def load_selected_columns(self):
        """从配置中加载已选择的列"""
        selected_columns = []
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if 'selected_columns' in config:
                    return config['selected_columns']
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return selected_columns

    def move_item(self, direction):
        """在两个列表之间移动项目"""
        if direction == 'left':
            source_list = self.available_listbox
            target_list = self.selected_listbox
        else:
            source_list = self.selected_listbox
            target_list = self.available_listbox
        
        selection = source_list.curselection()
        if not selection:
            return
        
        # 获取选中项
        item = source_list.get(selection[0])
        # 从源列表删除
        source_list.delete(selection[0])
        # 添加到目标列表
        target_list.insert(tk.END, item)
        
        # 自动保存更改
        self.save_column_selection()

    def move_item_updown(self, direction):
        """上下移动左侧列表中的项目"""
        selection = self.selected_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        if direction == 'up' and index > 0:
            self._swap_items(index, index - 1)
            self.selected_listbox.selection_set(index - 1)
        elif direction == 'down' and index < self.selected_listbox.size() - 1:
            self._swap_items(index, index + 1)
            self.selected_listbox.selection_set(index + 1)

    def _swap_items(self, pos1, pos2):
        """交换列表中两个位置的项目"""
        item1 = self.selected_listbox.get(pos1)
        item2 = self.selected_listbox.get(pos2)
        self.selected_listbox.delete(pos1)
        self.selected_listbox.insert(pos1, item2)
        self.selected_listbox.delete(pos2)
        self.selected_listbox.insert(pos2, item1)

    def save_column_selection(self, window=None):
        """保存列选择并可选关闭窗口"""
        # 获取当前选中的项目
        selected_items = list(self.selected_listbox.get(0, tk.END))
        
        # 重置所有配置为False
        for category in self.columns_config:
            for col in self.columns_config[category]:
                self.columns_config[category][col] = False
        
        # 设置选中项为True
        for item in selected_items:
            for category in self.columns_config:
                if item in self.columns_config[category]:
                    self.columns_config[category][item] = True
        
        # 保存配置
        config = {
            "output_dir": self.output_dir.get(),
            "last_input": self.input_entry.get(),
            "filename": self.filename_var.get(),
            "version": VERSION,
            "columns_config": self.columns_config,
            "selected_columns": selected_items  # 保存选中的列
        }
        
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存配置失败: {e}")
        
        # 如果提供了窗口参数，则关闭窗口
        if window:
            window.destroy()

def main():
    root = tk.Tk()
    app = ImageDetailExtractor(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main() 