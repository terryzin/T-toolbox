import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import subprocess
import json
import threading
from pathlib import Path
import shutil
import time
import concurrent.futures

class Split360GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("360° 图像分割工具")
        self.config_file = "360-spliter/config.json"
        self.is_processing = False
        self.current_process = None
        
        # 获取工具的默认安装路径
        self.default_tool_paths = [
            r"D:\Synthverse\Tools\Meshroom-2021.1.0\aliceVision\bin\aliceVision_utils_split360Images.exe",
        ]
        
        self.load_config()
        self.create_widgets()
        self.load_saved_values()
        
    def load_config(self):
        # 查找可用的工具路径
        tool_path = ""
        for path in self.default_tool_paths:
            if os.path.exists(path):
                tool_path = path
                break
                
        default_config = {
            "tool_path": tool_path,  # 使用找到的工具路径
            "input_path": "",
            "output_path": "",
            "clear_output": False,
            "splits": "6",
            "resolution": "1600",
            "threads": str(min(4, os.cpu_count() or 4))  # 默认线程数
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                    # 验证已保存的工具路径是否存在
                    if not os.path.exists(self.config.get("tool_path", "")):
                        self.config["tool_path"] = tool_path
            else:
                self.config = default_config
        except:
            self.config = default_config
            
    def save_config(self):
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=4)
            
    def create_widgets(self):
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 输入源
        ttk.Label(main_frame, text="输入源:").grid(row=0, column=0, sticky=tk.W)
        self.input_entry = ttk.Entry(main_frame, width=50)
        self.input_entry.grid(row=0, column=1, columnspan=2, sticky=(tk.W, tk.E))
        ttk.Button(main_frame, text="选文件", command=self.select_input_file).grid(row=0, column=3)
        ttk.Button(main_frame, text="选择文件夹", command=self.select_input_folder).grid(row=0, column=4)
        
        # 输出文件夹
        ttk.Label(main_frame, text="输出文件夹:").grid(row=1, column=0, sticky=tk.W)
        self.output_entry = ttk.Entry(main_frame, width=50)
        self.output_entry.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E))
        ttk.Button(main_frame, text="选择文件夹", command=self.select_output_folder).grid(row=1, column=3)
        ttk.Button(main_frame, text="打开文件夹", command=self.open_output_folder).grid(row=1, column=4)
        
        # 处理工具
        ttk.Label(main_frame, text="处理工具:").grid(row=2, column=0, sticky=tk.W)
        self.tool_entry = ttk.Entry(main_frame, width=50)
        self.tool_entry.grid(row=2, column=1, columnspan=2, sticky=(tk.W, tk.E))
        ttk.Button(main_frame, text="选择工具", command=self.select_tool).grid(row=2, column=3)
        
        # 清空输出目录选项
        self.clear_output_var = tk.BooleanVar()
        ttk.Checkbutton(main_frame, text="清空输出目录", variable=self.clear_output_var).grid(row=3, column=0, sticky=tk.W)
        
        # 分割数量
        ttk.Label(main_frame, text="分割数量:").grid(row=4, column=0, sticky=tk.W)
        self.splits_entry = ttk.Entry(main_frame, width=10)
        self.splits_entry.grid(row=4, column=1, sticky=tk.W)
        
        # 分辨率
        ttk.Label(main_frame, text="分辨率:").grid(row=5, column=0, sticky=tk.W)
        self.resolution_entry = ttk.Entry(main_frame, width=10)
        self.resolution_entry.grid(row=5, column=1, sticky=tk.W)
        
        # 线程数量
        ttk.Label(main_frame, text="线程数量:").grid(row=6, column=0, sticky=tk.W)
        self.threads_entry = ttk.Entry(main_frame, width=10)
        self.threads_entry.grid(row=6, column=1, sticky=tk.W)
        ttk.Label(main_frame, text=f"(建议 1-{os.cpu_count() or 4})").grid(row=6, column=2, sticky=tk.W)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        ttk.Label(main_frame, text="处理进度:").grid(row=7, column=0, sticky=tk.W)
        self.progress_bar = ttk.Progressbar(
            main_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.grid(row=7, column=1, columnspan=4, sticky=(tk.W, tk.E), padx=5)
        
        # 日志输出框 (行号+1)
        ttk.Label(main_frame, text="处理日志:").grid(row=8, column=0, sticky=tk.W)
        self.log_text = tk.Text(main_frame, height=10, width=70)
        self.log_text.grid(row=9, column=0, columnspan=5, sticky=(tk.W, tk.E))
        
        # 滚动条 (行号+1)
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=9, column=5, sticky=(tk.N, tk.S))
        self.log_text['yscrollcommand'] = scrollbar.set
        
        # 按钮框架 (行号+1)
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=10, column=0, columnspan=5, pady=10, sticky=(tk.W, tk.E))
        
        # 退出按钮靠左
        ttk.Button(button_frame, text="退出", command=self.root.quit).pack(side=tk.LEFT, padx=5)
        
        # 分割图像按钮靠右
        self.process_button = ttk.Button(button_frame, text="分割图像", command=self.process_images)
        self.process_button.pack(side=tk.RIGHT, padx=5)
        
        # 配置列权重以实现自适应
        main_frame.columnconfigure(1, weight=1)
        button_frame.pack_propagate(False)  # 防止按钮框架被内容压缩
        button_frame.configure(height=35)   # 设置按钮框架高度
        
    def load_saved_values(self):
        self.tool_entry.insert(0, self.config.get("tool_path", ""))
        self.input_entry.insert(0, self.config.get("input_path", ""))
        self.output_entry.insert(0, self.config.get("output_path", ""))
        self.clear_output_var.set(self.config.get("clear_output", False))
        self.splits_entry.insert(0, self.config.get("splits", "6"))
        self.resolution_entry.insert(0, self.config.get("resolution", "1600"))
        self.threads_entry.insert(0, self.config.get("threads", str(min(4, os.cpu_count() or 4))))
        
    def select_input_file(self):
        filename = filedialog.askopenfilename(filetypes=[("图像文件", "*.jpg *.jpeg *.png")])
        if filename:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, filename)
            
    def select_input_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, folder)
            
    def select_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, folder)
            
    def select_tool(self):
        filename = filedialog.askopenfilename(
            filetypes=[("可执行文件", "*.exe")],
            initialfile="aliceVision_utils_split360Images.exe",
            title="选择360°图像分割工具"
        )
        if filename:
            self.tool_entry.delete(0, tk.END)
            self.tool_entry.insert(0, filename)
            
    def open_output_folder(self):
        output_path = self.output_entry.get()
        if os.path.exists(output_path):
            os.startfile(output_path)
        else:
            messagebox.showwarning("警告", "输出文件夹不存在！")
            
    def update_log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        
    def process_images(self):
        if self.is_processing:
            if self.current_process:
                self.current_process.terminate()
                self.is_processing = False
                self.process_button.configure(text="分割图像")
                self.update_log("处理已停止")
            return

        # 验证工具路径
        tool_path = self.tool_entry.get()
        if not tool_path or not os.path.exists(tool_path):
            messagebox.showerror("错误", "请选择正确的处理工具！")
            return

        # 验证输入和输出路径
        input_path = self.input_entry.get()
        output_path = self.output_entry.get()
        if not all([input_path, output_path, self.splits_entry.get(), self.resolution_entry.get()]):
            messagebox.showerror("错误", "请填写所有必要的字段！")
            return

        # 验证并获取线程数
        try:
            threads = int(self.threads_entry.get())
            if threads < 1:
                raise ValueError("线程数必须大于0")
        except ValueError as e:
            messagebox.showerror("错误", f"无效的线程数: {str(e)}")
            return

        # 获取所有需要处理的图片文件
        image_files = []
        if os.path.isfile(input_path):
            # 单个文件
            if input_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                image_files.append(input_path)
        else:
            # 文件夹，收集所有图片文件
            for root, _, files in os.walk(input_path):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                        image_files.append(os.path.join(root, file))

        if not image_files:
            messagebox.showerror("错误", "未找到可处理的图片文件！")
            return

        # 清空或创建主输出目录
        try:
            if self.clear_output_var.get() and os.path.exists(output_path):
                self.update_log(f"正在清空输���目录: {output_path}")
                shutil.rmtree(output_path)
            os.makedirs(output_path, exist_ok=True)
        except Exception as e:
            self.update_log(f"处理输出目录失败: {str(e)}")
            messagebox.showerror("错误", f"处理输出目录失败: {str(e)}")
            return

        # 保存配置
        self.config.update({
            "tool_path": tool_path,
            "input_path": input_path,
            "output_path": output_path,
            "clear_output": self.clear_output_var.get(),
            "splits": self.splits_entry.get(),
            "resolution": self.resolution_entry.get(),
            "threads": str(threads)
        })
        self.save_config()

        # 设置处理状态
        self.is_processing = True
        self.process_button.configure(text="停止")
        
        # 使用用户设置的线程数
        max_workers = min(threads, len(image_files))
        self.update_log(f"创建{max_workers}个处理线程")
        
        # 启动处理线程
        processing_thread = threading.Thread(
            target=self.process_multiple_images,
            args=(image_files, tool_path, output_path, max_workers)
        )
        processing_thread.daemon = True
        processing_thread.start()

    def process_multiple_images(self, image_files, tool_path, base_output_path, max_workers):
        try:
            # 重置进度条
            self.progress_var.set(0)
            total_files = len(image_files)
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_file = {}
                for img_file in image_files:
                    cmd = [
                        tool_path,
                        "-i", img_file,
                        "-o", base_output_path,
                        "--equirectangularNbSplits", self.splits_entry.get(),
                        "--equirectangularSplitResolution", self.resolution_entry.get()
                    ]
                    
                    future = executor.submit(self.run_single_process, cmd, img_file)
                    future_to_file[future] = img_file
                
                completed = 0
                for future in concurrent.futures.as_completed(future_to_file):
                    img_file = future_to_file[future]
                    completed += 1
                    try:
                        success = future.result()
                        status = "成功" if success else "失败"
                        # 更新进度条
                        progress = (completed / total_files) * 100
                        self.progress_var.set(progress)
                        self.update_log(f"处理进度: [{completed}/{total_files}] {os.path.basename(img_file)} - {status}")
                    except Exception as e:
                        self.update_log(f"处理失败 {os.path.basename(img_file)}: {str(e)}")
                    
        except Exception as e:
            self.update_log(f"多线程处理发生错误: {str(e)}")
        finally:
            self.is_processing = False
            self.process_button.configure(text="分割图像")
            self.update_log("所有任务处理完成")

    def run_single_process(self, cmd, img_file):
        try:
            self.update_log(f"开始处理: {os.path.basename(img_file)}")
            # 使用 subprocess.PIPE 捕获输出，不显示命令行窗口
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True  # 使用text=True替代universal_newlines=True
            )
            
            # 读取输出
            stdout, stderr = process.communicate()
            
            if stdout:
                self.update_log(stdout.strip())
            if stderr:
                self.update_log(f"警告/错误: {stderr.strip()}")
            
            return process.returncode == 0
        except Exception as e:
            self.update_log(f"处理出错 {os.path.basename(img_file)}: {str(e)}")
            return False

def main():
    root = tk.Tk()
    app = Split360GUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 