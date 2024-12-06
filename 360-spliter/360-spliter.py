import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import subprocess
import json
import threading
from pathlib import Path
import shutil
import time

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
            "resolution": "1600"
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
        
        # 日志输出框
        ttk.Label(main_frame, text="处理日志:").grid(row=6, column=0, sticky=tk.W)
        self.log_text = tk.Text(main_frame, height=10, width=70)
        self.log_text.grid(row=7, column=0, columnspan=5, sticky=(tk.W, tk.E))
        
        # 滚动条
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=7, column=5, sticky=(tk.N, tk.S))
        self.log_text['yscrollcommand'] = scrollbar.set
        
        # 按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=5, pady=10, sticky=(tk.W, tk.E))
        
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
        if not tool_path:
            messagebox.showerror("错误", "请选择处理工具！")
            return
        if not os.path.exists(tool_path):
            messagebox.showerror("错误", 
                "找不到处理工具，请检查工具路径是否正确！\n"
                "默认工具路径：\n" + "\n".join(self.default_tool_paths))
            return
            
        # 验证输入
        if not all([self.tool_entry.get(), self.input_entry.get(), 
                   self.output_entry.get(), self.splits_entry.get(), 
                   self.resolution_entry.get()]):
            messagebox.showerror("错误", "请填写所有必要的字段！")
            return

        output_path = self.output_entry.get()
        
        # 清空输出目录
        if self.clear_output_var.get():
            try:
                if os.path.exists(output_path):
                    # 使用 update_log 记录清空操作
                    self.update_log(f"正在清空输出目录: {output_path}")
                    for item in os.listdir(output_path):
                        item_path = os.path.join(output_path, item)
                        try:
                            if os.path.isfile(item_path):
                                os.unlink(item_path)
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                        except Exception as e:
                            self.update_log(f"清除项目失败: {item_path} - {str(e)}")
                
                # 确保输出目录存在
                os.makedirs(output_path, exist_ok=True)
                self.update_log("输出目录已清空并重新创建")
                
            except Exception as e:
                self.update_log(f"清空输出目录失败: {str(e)}")
                messagebox.showerror("错误", f"清空输出目录失败: {str(e)}")
                return
        else:
            # 如果不清空，至少确保输出目录存在
            try:
                os.makedirs(output_path, exist_ok=True)
            except Exception as e:
                self.update_log(f"创建输出目录失败: {str(e)}")
                messagebox.showerror("错误", f"创建输出目录失败: {str(e)}")
                return
        
        # 保存当前配置
        self.config.update({
            "tool_path": tool_path,
            "input_path": self.input_entry.get(),
            "output_path": output_path,
            "clear_output": self.clear_output_var.get(),
            "splits": self.splits_entry.get(),
            "resolution": self.resolution_entry.get()
        })
        self.save_config()
        
        # 构建命令
        cmd = [
            self.tool_entry.get(),
            "-i", self.input_entry.get(),
            "-o", self.output_entry.get(),
            "--equirectangularNbSplits", self.splits_entry.get(),
            "--equirectangularSplitResolution", self.resolution_entry.get()
        ]
        
        self.is_processing = True
        self.process_button.configure(text="停止")
        
        # 在新线程中执行命令
        thread = threading.Thread(target=self.run_process, args=(cmd,))
        thread.daemon = True
        thread.start()
        
    def run_process(self, cmd):
        try:
            # 在日志中显示完整命令
            self.update_log("开始处理...")
            self.update_log("执行命令:")
            self.update_log(" ".join(cmd))
            self.update_log("-" * 50)  # 添加分隔线
            
            # 在 Windows 上创建新的控制台窗口
            creation_flags = subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            
            # 移除 stdout 和 stderr 的重定向，让输出直接显示在新窗口中
            self.current_process = subprocess.Popen(
                cmd,
                creationflags=creation_flags
            )
            
            # 等待进程完成
            returncode = self.current_process.wait()
            
            if returncode == 0:
                self.update_log("-" * 50)
                self.update_log("处理完成！")
            else:
                self.update_log("-" * 50)
                self.update_log(f"处理失败，返回码: {returncode}")
                
        except Exception as e:
            self.update_log(f"发生错误: {str(e)}")
        finally:
            self.is_processing = False
            self.current_process = None
            self.process_button.configure(text="分割图像")

def main():
    root = tk.Tk()
    app = Split360GUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 