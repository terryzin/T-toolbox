import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
from PIL import Image
import threading
from pathlib import Path
import concurrent.futures
import time

class ImageMixer:
    def __init__(self, root):
        self.root = root
        self.root.title("图像通道混合工具")
        
        # 配置文件路径
        self.config_file = "image-mixer/image_mixer_config.json"
        
        # 状态变量
        self.is_processing = False
        self.should_stop = False
        self.executor = None
        
        self.create_ui()
        self.load_config()
        
    def create_ui(self):
        # 设置窗口最小大小和默认大小
        self.root.minsize(800, 500)
        self.root.geometry("800x500")
        
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置主窗口的网格权重，使其可以自适应调整大小
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # 数据源选择
        ttk.Label(main_frame, text="输入源:").grid(row=0, column=0, sticky=tk.W)
        self.data_source = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.data_source).grid(row=0, column=1, sticky=(tk.W, tk.E))
        ttk.Button(main_frame, text="选择文件", command=lambda: self.browse_data_source(True)).grid(row=0, column=2)
        ttk.Button(main_frame, text="选择文件夹", command=lambda: self.browse_data_source(False)).grid(row=0, column=3)
        
        # Alpha源选择
        ttk.Label(main_frame, text="Alpha源:").grid(row=1, column=0, sticky=tk.W)
        self.alpha_source = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.alpha_source).grid(row=1, column=1, sticky=(tk.W, tk.E))
        ttk.Button(main_frame, text="选择文件", command=lambda: self.browse_alpha_source(True)).grid(row=1, column=2)
        ttk.Button(main_frame, text="选择文件夹", command=lambda: self.browse_alpha_source(False)).grid(row=1, column=3)
        
        # Alpha通道映射选择
        ttk.Label(main_frame, text="Alpha通道映射:").grid(row=2, column=0, sticky=tk.W)
        self.channel_map = tk.StringVar(value="Alpha")
        channels = ["Red", "Green", "Blue", "Alpha"]
        channel_combo = ttk.Combobox(main_frame, textvariable=self.channel_map, values=channels, state="readonly")
        channel_combo.grid(row=2, column=1, sticky=(tk.W, tk.E))
        
        # Alpha反转选项
        self.alpha_invert = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="Alpha反转", variable=self.alpha_invert).grid(row=2, column=2, sticky=tk.W)
        
        # 输出目录选择
        ttk.Label(main_frame, text="输出目录:").grid(row=3, column=0, sticky=tk.W)
        self.output_dir = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.output_dir).grid(row=3, column=1, sticky=(tk.W, tk.E))
        ttk.Button(main_frame, text="选择文件夹", command=self.browse_output_dir).grid(row=3, column=2)
        ttk.Button(main_frame, text="打开目录", command=self.open_output_dir).grid(row=3, column=3)
        
        # 输出前缀
        ttk.Label(main_frame, text="输出前缀:").grid(row=4, column=0, sticky=tk.W)
        self.output_prefix = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.output_prefix).grid(row=4, column=1, sticky=(tk.W, tk.E))
        
        # 清空输出目录选项
        self.clear_output = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="清空输出目录", variable=self.clear_output).grid(row=5, column=0, columnspan=2, sticky=tk.W)
        
        # 多线程设置
        ttk.Label(main_frame, text="处理线程数:").grid(row=5, column=2, sticky=tk.E)
        self.thread_count = tk.StringVar(value="1")
        thread_entry = ttk.Entry(main_frame, textvariable=self.thread_count, width=5)
        thread_entry.grid(row=5, column=3, sticky=tk.W)
        
        # 进度条
        progress_frame = ttk.Frame(main_frame)
        progress_frame.grid(row=6, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=10)
        self.progress_var = tk.StringVar(value="准备就绪")
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(side=tk.TOP, anchor=tk.W)
        self.progress = ttk.Progressbar(progress_frame, length=300, mode='determinate')
        self.progress.pack(fill=tk.X, expand=True)
        
        # 日志输出框
        self.log_text = tk.Text(main_frame, height=8)
        self.log_text.grid(row=7, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=7, column=4, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=10)
        
        # 转换和退出按钮
        ttk.Button(button_frame, text="退出", command=self.root.quit).pack(side=tk.LEFT, padx=5)
        self.convert_button = ttk.Button(button_frame, text="转换", command=self.toggle_conversion)
        self.convert_button.pack(side=tk.RIGHT, padx=5)
        
        # 配置列权重以实现自适应
        main_frame.grid_columnconfigure(1, weight=1)  # 让第二列（输入框所在列）可以自适应拉伸
        main_frame.grid_rowconfigure(7, weight=1)     # 让日志框可以自适应拉伸
        
        # 设置所有控件的内边距
        for child in main_frame.winfo_children():
            child.grid_configure(padx=5, pady=3)
        
    def browse_data_source(self, is_file):
        if is_file:
            path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.tiff")])
        else:
            path = filedialog.askdirectory()
        if path:
            self.data_source.set(path)
            
    def browse_alpha_source(self, is_file):
        if is_file:
            path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.tiff")])
        else:
            path = filedialog.askdirectory()
        if path:
            self.alpha_source.set(path)
            
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
            "data_source": self.data_source.get(),
            "alpha_source": self.alpha_source.get(),
            "channel_map": self.channel_map.get(),
            "output_dir": self.output_dir.get(),
            "output_prefix": self.output_prefix.get(),
            "clear_output": self.clear_output.get(),
            "alpha_invert": self.alpha_invert.get(),
            "thread_count": self.thread_count.get()
        }
        with open(self.config_file, "w") as f:
            json.dump(config, f)
            
    def load_config(self):
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
                self.data_source.set(config.get("data_source", ""))
                self.alpha_source.set(config.get("alpha_source", ""))
                self.channel_map.set(config.get("channel_map", "Alpha"))
                self.output_dir.set(config.get("output_dir", ""))
                self.output_prefix.set(config.get("output_prefix", ""))
                self.clear_output.set(config.get("clear_output", False))
                self.alpha_invert.set(config.get("alpha_invert", False))
                self.thread_count.set(config.get("thread_count", "1"))
        except FileNotFoundError:
            pass
            
    def toggle_conversion(self):
        if not self.is_processing:
            self.start_conversion()
        else:
            self.should_stop = True
            if self.executor:
                self.executor.shutdown(wait=False)
                self.executor = None
            self.log("正在停止处理...")
            
    def start_conversion(self):
        # 验证输入
        if not os.path.exists(self.data_source.get()):
            messagebox.showerror("错误", "数据源文件夹不存在")
            return
        if not os.path.exists(self.alpha_source.get()):
            messagebox.showerror("错误", "Alpha源不存在")
            return
        if not os.path.exists(self.output_dir.get()):
            os.makedirs(self.output_dir.get())
            
        # 清空输出目录
        if self.clear_output.get():
            for file in os.listdir(self.output_dir.get()):
                file_path = os.path.join(self.output_dir.get(), file)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    
        self.is_processing = True
        self.should_stop = False
        self.convert_button.configure(text="停止")
        
        # 启动转换线程
        thread = threading.Thread(target=self.process_images)
        thread.start()
        
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

            data_source = self.data_source.get()
            is_single_file = os.path.isfile(data_source)
            
            if is_single_file:
                data_files = [os.path.basename(data_source)]
                data_source_dir = os.path.dirname(data_source)
            else:
                data_source_dir = data_source
                data_files = sorted([f for f in os.listdir(data_source_dir) 
                                   if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff'))])
            
            alpha_source = self.alpha_source.get()
            if os.path.isfile(alpha_source):
                alpha_files = [alpha_source] * len(data_files)
                alpha_source_dir = os.path.dirname(alpha_source)
            else:
                alpha_source_dir = alpha_source
                alpha_files = sorted([f for f in os.listdir(alpha_source_dir)
                                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff'))])
                
            total = min(len(data_files), len(alpha_files))
            self.progress["maximum"] = total
            
            channel_map = {
                "Red": 0,
                "Green": 1,
                "Blue": 2,
                "Alpha": 3
            }

            # 创建任务列表
            tasks = list(zip(data_files, alpha_files))
            processed_count = 0
            
            # 创建线程池
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=thread_count)
            futures = []
            
            # 提交所有任务
            for data_file, alpha_file in tasks:
                if self.should_stop:
                    break
                    
                future = self.executor.submit(
                    self.process_single_image,
                    data_file,
                    data_source_dir,
                    alpha_file if os.path.isfile(self.alpha_source.get()) else os.path.join(alpha_source_dir, alpha_file),
                    is_single_file,
                    channel_map
                )
                futures.append(future)
            
            # 处理完成的任务
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

    def process_single_image(self, data_file, data_source_dir, alpha_path, is_single_file, channel_map):
        try:
            data_path = os.path.join(data_source_dir, data_file) if not is_single_file else data_source_dir
            
            # 打开图像
            data_img = Image.open(data_path).convert('RGBA')
            alpha_img = Image.open(alpha_path).convert('RGBA')
            
            # 获取通道数据
            data_channels = list(data_img.split())
            alpha_channels = list(alpha_img.split())
            
            # 替换Alpha通道
            selected_channel = channel_map[self.channel_map.get()]
            alpha_channel = alpha_channels[selected_channel]
            
            # 如果启用了Alpha反转，反转alpha通道
            if self.alpha_invert.get():
                alpha_channel = Image.eval(alpha_channel, lambda x: 255 - x)
            
            data_channels[3] = alpha_channel
            
            # 合并通道
            result = Image.merge('RGBA', data_channels)
            
            # 保存结果
            output_name = os.path.splitext(data_file)[0]
            if self.output_prefix.get():
                output_name = self.output_prefix.get() + output_name
            output_path = os.path.join(self.output_dir.get(), output_name + '.png')
            
            # 直接以PNG格式保存，保留透明度
            result.save(output_path, 'PNG')
            
            alpha_name = os.path.basename(alpha_path)
            self.log(f"已处理: {data_file} -> {alpha_name} -> {os.path.basename(output_path)}")
            return True
        except Exception as e:
            self.log(f"处理 {data_file} 时出错: {str(e)}")
            return False

def main():
    root = tk.Tk()
    app = ImageMixer(root)
    root.mainloop()

if __name__ == "__main__":
    main()
