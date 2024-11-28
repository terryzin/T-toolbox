import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import threading
import shutil
from pathlib import Path
import queue
import logging
import time

class FileHelper:
    def __init__(self, root):
        self.root = root
        self.root.title("文件处理工具")
        self.root.minsize(600, 500)
        
        # 获取程序所在目录
        self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.app_dir, 'config.json')
        
        # 创建变量
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.output_prefix = tk.StringVar(value="")
        self.clear_output = tk.BooleanVar(value=False)
        self.thread_count = tk.StringVar(value="1")
        self.separator = tk.StringVar(value="_")
        self.mask_path = tk.StringVar()
        
        # 添加处理统计相关变量
        self.start_time = None
        self.total_files = 0
        self.processed_files = 0
        self.is_processing = False
        self.stop_flag = False
        self.queue = queue.Queue()
        
        self.create_widgets()
        self.load_config()
        
    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # 输入源框架
        row = 0
        ttk.Label(main_frame, text="输入源:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        input_entry = ttk.Entry(main_frame, textvariable=self.input_path)
        input_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(main_frame, text="选择文件", command=self.select_files).grid(row=row, column=2, padx=2)
        ttk.Button(main_frame, text="选择文件夹", command=self.select_folder).grid(row=row, column=3, padx=2)
        
        # 输出目录框架
        row += 1
        ttk.Label(main_frame, text="输出目录:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        output_entry = ttk.Entry(main_frame, textvariable=self.output_path)
        output_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=5)
        ttk.Button(main_frame, text="选择文件夹", command=self.select_output).grid(row=row, column=2, padx=2)
        ttk.Button(main_frame, text="打开目录", command=self.open_output).grid(row=row, column=3, padx=2)
        
        # 输出前缀
        row += 1
        ttk.Label(main_frame, text="输出前缀:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(main_frame, textvariable=self.output_prefix).grid(row=row, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # 选项框架
        row += 1
        options_frame = ttk.Frame(main_frame)
        options_frame.grid(row=row, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Checkbutton(options_frame, text="清空输出目录", variable=self.clear_output).pack(side=tk.LEFT, padx=5)
        ttk.Label(options_frame, text="处理线程数:").pack(side=tk.RIGHT, padx=5)
        ttk.Entry(options_frame, textvariable=self.thread_count, width=5).pack(side=tk.RIGHT)
        
        # 拍平目录框架
        row += 1
        flatten_frame = ttk.LabelFrame(main_frame, text="拍平目录", padding="5")
        flatten_frame.grid(row=row, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=5)
        flatten_frame.columnconfigure(1, weight=1)
        
        # 左侧分隔符控件
        separator_frame = ttk.Frame(flatten_frame)
        separator_frame.pack(side=tk.LEFT, fill=tk.X)
        ttk.Label(separator_frame, text="分隔符:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(separator_frame, textvariable=self.separator, width=5).pack(side=tk.LEFT, padx=5)
        
        # 右侧拍平按钮
        self.flatten_button = ttk.Button(flatten_frame, text="拍平目录", command=self.toggle_flatten)
        self.flatten_button.pack(side=tk.RIGHT, padx=5)
        
        # 生成Mask框架
        row += 1
        mask_frame = ttk.LabelFrame(main_frame, text="生成Mask", padding="5")
        mask_frame.grid(row=row, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(mask_frame, text="Mask文件:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(mask_frame, textvariable=self.mask_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(mask_frame, text="选择文件", command=self.select_mask_file).pack(side=tk.LEFT, padx=5)
        self.mask_button = ttk.Button(mask_frame, text="生成Mask", command=self.toggle_mask)
        self.mask_button.pack(side=tk.LEFT, padx=5)
        
        # 进度条
        row += 1
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(main_frame, length=100, mode='determinate', variable=self.progress_var)
        self.progress.grid(row=row, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=5)
        
        # 日志框架
        row += 1
        log_frame = ttk.LabelFrame(main_frame, text="准备就绪", padding="5")
        log_frame.grid(row=row, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = tk.Text(log_frame, height=8, wrap=tk.WORD)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text['yscrollcommand'] = scrollbar.set
        
        # 按钮框架 - 修改布局
        row += 1
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=4, sticky=(tk.W), pady=5)
        
        ttk.Button(button_frame, text="退出", command=self.on_closing).pack(side=tk.LEFT, padx=5)
        
        # 配置主框架的列权重
        main_frame.columnconfigure(1, weight=1)
        
    def load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.output_prefix.set(config.get('output_prefix', ''))
                    self.thread_count.set(config.get('thread_count', '1'))
                    self.separator.set(config.get('separator', '_'))
                    self.clear_output.set(config.get('clear_output', False))
                    # 恢复上次的路径
                    if 'last_input_path' in config:
                        self.input_path.set(config['last_input_path'])
                    if 'last_output_path' in config:
                        self.output_path.set(config['last_output_path'])
                    if 'last_mask_path' in config:
                        self.mask_path.set(config['last_mask_path'])
        except Exception as e:
            self.log(f"加载配置失败: {str(e)}")
            
    def save_config(self):
        config = {
            'output_prefix': self.output_prefix.get(),
            'thread_count': self.thread_count.get(),
            'separator': self.separator.get(),
            'clear_output': self.clear_output.get(),
            'last_input_path': self.input_path.get(),
            'last_output_path': self.output_path.get(),
            'last_mask_path': self.mask_path.get()
        }
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.log(f"保存配置失败: {str(e)}")
            
    def select_files(self):
        files = filedialog.askopenfilenames()
        if files:
            self.input_path.set(';'.join(files))
            
    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_path.set(folder)
            
    def select_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_path.set(folder)
            
    def open_output(self):
        if self.output_path.get():
            os.startfile(self.output_path.get())
            
    def log(self, message):
        self.queue.put(message)
        self.root.after(100, self.process_log_queue)
        
    def process_log_queue(self):
        while not self.queue.empty():
            message = self.queue.get()
            self.log_text.insert(tk.END, message + '\n')
            self.log_text.see(tk.END)
            
    def toggle_flatten(self):
        if not self.is_processing:
            self.start_flatten()
        else:
            self.stop_flatten()

    def start_flatten(self):
        if not self.input_path.get() or not self.output_path.get():
            messagebox.showerror("错误", "请选择输入和输出路径")
            return
        
        try:
            # 重置标志和计数器
            self.stop_flag = False
            self.processed_files = 0
            self.start_time = time.time()
            
            # 如果勾选了清空输出目录，先清空
            if self.clear_output.get():
                self.clear_output_directory()
            
            input_path = Path(self.input_path.get())
            
            # 计算总文件数
            self.total_files = sum(1 for _ in input_path.rglob('*') if _.is_file())
            if self.total_files == 0:
                messagebox.showwarning("警告", "没有找到需要处理的文件")
                return
            
            # 更新按钮状态
            self.flatten_button.configure(text="停止")
            self.is_processing = True
            
            # 创建并启动工作线程
            thread_count = max(1, min(int(self.thread_count.get()), 32))
            self.work_threads = []
            
            # 创建文件队列
            self.file_queue = queue.Queue()
            for file_path in input_path.rglob('*'):
                if file_path.is_file():
                    self.file_queue.put(file_path)
            
            # 启动工作线程
            for _ in range(thread_count):
                t = threading.Thread(target=self.process_files)
                t.daemon = True
                t.start()
                self.work_threads.append(t)
                
        except Exception as e:
            self.log(f"错误: {str(e)}")
            messagebox.showerror("错误", str(e))
            self.stop_flatten()

    def process_files(self):
        while not self.stop_flag:
            try:
                file_path = self.file_queue.get_nowait()
            except queue.Empty:
                break
            
            try:
                input_path = Path(self.input_path.get())
                output_path = Path(self.output_path.get())
                prefix = self.output_prefix.get()
                separator = self.separator.get()
                
                relative_path = file_path.relative_to(input_path)
                parts = list(relative_path.parts[:-1])
                new_name = prefix + separator + separator.join(parts + [file_path.name]) if prefix else separator.join(parts + [file_path.name])
                
                output_file = output_path / new_name
                output_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, output_file)
                
                with threading.Lock():
                    self.processed_files += 1
                    self.progress_var.set((self.processed_files / self.total_files) * 100)
                    self.log(f"已处理: {file_path} -> {output_file}")
                    
                    # 检查是否所有文件都处理完成
                    if self.processed_files >= self.total_files:
                        self.root.after(100, self.finish_processing)
                        
            except Exception as e:
                self.log(f"处理文件失败 {file_path}: {str(e)}")
            finally:
                self.file_queue.task_done()

    def stop_flatten(self):
        self.stop_flag = True
        self.is_processing = False
        self.flatten_button.configure(text="拍平目录")
        
        # 清空队列，防止线程阻塞
        try:
            while True:
                self.file_queue.get_nowait()
                self.file_queue.task_done()
        except queue.Empty:
            pass
        
        # 等待所有线程完成，但设置超时
        if hasattr(self, 'work_threads'):
            for t in self.work_threads:
                t.join(timeout=0.5)  # 设置0.5秒超时
        
        # 显示中断信息
        elapsed_time = time.time() - self.start_time
        self.log("\n处理已中断")
        self.log(f"总计处理文件: {self.processed_files}/{self.total_files}")
        self.log(f"用时: {elapsed_time:.2f}秒")
        self.log(f"平均速度: {self.processed_files/elapsed_time:.2f}文件/秒")

    def finish_processing(self):
        self.stop_flag = True
        self.is_processing = False
        
        # 根据当前活动的按钮恢复其状态
        if hasattr(self, 'flatten_button'):
            self.flatten_button.configure(text="拍平目录")
        if hasattr(self, 'mask_button'):
            self.mask_button.configure(text="生成Mask")
        
        # 显示完成统计信息
        elapsed_time = time.time() - self.start_time
        self.log("\n处理完成")
        self.log(f"总计处理文件: {self.processed_files}个")
        self.log(f"用时: {elapsed_time:.2f}秒")
        self.log(f"平均速度: {self.processed_files/elapsed_time:.2f}文件/秒")
        self.log(f"使用线程数: {self.thread_count.get()}")
        
        # 移除弹框提示
        # messagebox.showinfo("完成", "文件处理完成！")

    def on_closing(self):
        if self.is_processing:
            if messagebox.askokcancel("确认", "正在处理中，确定要退出吗？"):
                self.stop_flatten()
                self.save_config()
                self.root.destroy()
        else:
            self.save_config()
            self.root.destroy()

    def clear_output_directory(self):
        if self.output_path.get():
            try:
                output_dir = Path(self.output_path.get())
                if output_dir.exists():
                    for item in output_dir.glob('*'):
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)
                    self.log("已清空输出目录")
                else:
                    # 如果目录不存在，创建它
                    output_dir.mkdir(parents=True, exist_ok=True)
                    self.log("创建输出目录")
            except Exception as e:
                self.log(f"清空输出目录失败: {str(e)}")
                raise

    def select_mask_file(self):
        file = filedialog.askopenfilename()
        if file:
            self.mask_path.set(file)

    def toggle_mask(self):
        if not self.is_processing:
            self.start_mask_generation()
        else:
            self.stop_mask_generation()

    def start_mask_generation(self):
        if not self.input_path.get() or not self.output_path.get() or not self.mask_path.get():
            messagebox.showerror("错误", "请选择输入源、输出目录和Mask文件")
            return
        
        try:
            # 重置标志和计数器
            self.stop_flag = False
            self.processed_files = 0
            self.start_time = time.time()
            
            # 如果勾选了清空输出目录，先清空
            if self.clear_output.get():
                self.clear_output_directory()
            
            # 获取输入文件列表
            input_path = Path(self.input_path.get())
            if input_path.is_file():
                self.total_files = 1
                files = [input_path]
            else:
                files = list(input_path.rglob('*'))
                self.total_files = sum(1 for f in files if f.is_file())
            
            if self.total_files == 0:
                messagebox.showwarning("警告", "没有找到需要处理的文件")
                return
            
            # 更新按钮状态
            self.mask_button.configure(text="停止")
            self.is_processing = True
            
            # 创建并启动工作线程
            thread_count = max(1, min(int(self.thread_count.get()), 32))
            self.work_threads = []
            
            # 创建文件队列
            self.file_queue = queue.Queue()
            for file_path in files:
                if file_path.is_file():
                    self.file_queue.put(file_path)
            
            # 启动工作线程
            for _ in range(thread_count):
                t = threading.Thread(target=self.process_mask_files)
                t.daemon = True
                t.start()
                self.work_threads.append(t)
                
        except Exception as e:
            self.log(f"错误: {str(e)}")
            messagebox.showerror("错误", str(e))
            self.stop_mask_generation()

    def process_mask_files(self):
        while not self.stop_flag:
            try:
                file_path = self.file_queue.get_nowait()
            except queue.Empty:
                break
            
            try:
                input_path = Path(self.input_path.get())
                output_path = Path(self.output_path.get())
                mask_path = Path(self.mask_path.get())
                
                # 计算输出文件路径
                if input_path.is_file():
                    output_file = output_path / file_path.name
                else:
                    relative_path = file_path.relative_to(input_path)
                    output_file = output_path / relative_path
                
                # 创建输出目录
                output_file.parent.mkdir(parents=True, exist_ok=True)
                
                # 复制mask文件并重命名
                shutil.copy2(mask_path, output_file)
                
                with threading.Lock():
                    self.processed_files += 1
                    self.progress_var.set((self.processed_files / self.total_files) * 100)
                    self.log(f"已处理: {file_path.name} -> {output_file}")
                    
                    # 检查是否所有文件都处理完成
                    if self.processed_files >= self.total_files:
                        self.root.after(100, self.finish_processing)
                        
            except Exception as e:
                self.log(f"处理文件失败 {file_path}: {str(e)}")
            finally:
                self.file_queue.task_done()

    def stop_mask_generation(self):
        self.stop_flag = True
        self.is_processing = False
        self.mask_button.configure(text="生成Mask")
        
        # 清空队列，防止线程阻塞
        try:
            while True:
                self.file_queue.get_nowait()
                self.file_queue.task_done()
        except queue.Empty:
            pass
        
        # 等待所有线程完成，但设置超时
        if hasattr(self, 'work_threads'):
            for t in self.work_threads:
                t.join(timeout=0.5)  # 设置0.5秒超时
        
        # 显示中断信息
        elapsed_time = time.time() - self.start_time
        self.log("\n处理已中断")
        self.log(f"总计处理文件: {self.processed_files}/{self.total_files}")
        self.log(f"用时: {elapsed_time:.2f}秒")
        self.log(f"平均速度: {self.processed_files/elapsed_time:.2f}文件/秒")

def main():
    root = tk.Tk()
    app = FileHelper(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main() 