import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
from PIL import Image, ImageTk
import subprocess
import warnings
import logging
from tkinter import font

# 配置日志
logging.basicConfig(level=logging.DEBUG)
warnings.filterwarnings("ignore", category=UserWarning)

class ToolIcon(tk.Label):
    def __init__(self, parent, tool_info, placeholder_image, position=None, launcher=None):
        super().__init__(parent)
        self.parent = parent
        self.tool_info = tool_info
        self.position = position
        self.launcher = launcher
        self.is_dragging = False  # 添加拖拽标志
        
        # 调整图标大小
        ICON_SIZE = 60  # 将图标尺寸从64改为60
        
        # 加载图标
        try:
            if not os.path.exists(tool_info.get("icon", placeholder_image)):
                logging.warning(f"图标文件不存在: {tool_info.get('icon')}")
                raise FileNotFoundError
                
            image = Image.open(tool_info.get("icon", placeholder_image))
            if image.mode in ('RGBA', 'RGB'):
                image = image.convert('RGBA')
            image = image.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(image)
        except Exception as e:
            logging.warning(f"加载图标失败: {str(e)}")
            try:
                if not os.path.exists(placeholder_image):
                    logging.error(f"默认图标也不存在: {placeholder_image}")
                    # 创建一个空白图片作为替代
                    image = Image.new('RGBA', (ICON_SIZE, ICON_SIZE), 'gray')
                else:
                    image = Image.open(placeholder_image)
                    image = image.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
                self.photo = ImageTk.PhotoImage(image)
            except Exception as e:
                logging.error(f"创建默认图标失败: {str(e)}")
                return
            
        # 美化图标显示
        self.configure(
            image=self.photo,
            width=ICON_SIZE,
            height=ICON_SIZE,
            bg='#f0f0f0',  # 设置背景色
            cursor="hand2"  # 鼠标悬停时显示手型
        )
        
        # 美化工具名称标签
        self.name_label = tk.Label(
            parent,
            text=tool_info.get("name", "未命名工具"),
            font=('Microsoft YaHei UI', 8),  # 减小字体大小
            bg='#f0f0f0'
        )
        
        # 绑定事件
        self.bind("<ButtonPress-1>", self.on_drag_start)
        self.bind("<B1-Motion>", self.on_drag_motion)
        self.bind("<ButtonRelease-1>", self.on_drag_release)
        
    def on_drag_start(self, event):
        self.is_dragging = False  # 初始化拖拽标志
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        
    def on_drag_motion(self, event):
        # 如果移动距离超过阈值，标记为拖拽
        if abs(event.x - self._drag_start_x) > 5 or abs(event.y - self._drag_start_y) > 5:
            self.is_dragging = True
            
        if self.is_dragging:
            x = self.winfo_x() + event.x - self._drag_start_x
            y = self.winfo_y() + event.y - self._drag_start_y
            self.place(x=x, y=y)
            self.name_label.place(x=x, y=y+70)
        
    def on_drag_release(self, event):
        if not self.is_dragging:
            # 如果不是拖拽，则执行启动工具
            self.launch_tool(event)
            return
            
        # 以下是原有的拖拽释放逻辑
        grid_size = 100
        target_x = round((self.winfo_x() - 25) / grid_size)
        target_y = round((self.winfo_y() - 40) / grid_size)
        target_position = target_y * 3 + target_x
        
        if 0 <= target_x < 3 and 0 <= target_y < 3 and target_position != self.position:
            # 获取目标位置的图标
            target_icon = self.parent.icons[target_position]
            
            # 交换位置
            old_x = (self.position % 3) * grid_size + 25
            old_y = (self.position // 3) * grid_size + 40
            new_x = target_x * grid_size + 25
            new_y = target_y * grid_size + 40
            
            # 更新两个图标的位置
            self.place(x=new_x, y=new_y)
            self.name_label.place(x=new_x, y=new_y+70)
            target_icon.place(x=old_x, y=old_y)
            target_icon.name_label.place(x=old_x, y=old_y+70)
            
            # 交换位置信息
            self.parent.icons[self.position], self.parent.icons[target_position] = \
                self.parent.icons[target_position], self.parent.icons[self.position]
            self.position, target_icon.position = target_position, self.position
            
            # 保存新的位置配置
            self.launcher.save_config()
        else:
            # 返回原位置
            x = (self.position % 3) * grid_size + 25
            y = (self.position // 3) * grid_size + 40
            self.place(x=x, y=y)
            self.name_label.place(x=x, y=y+70)

    def launch_tool(self, event):
        script_path = self.tool_info.get("script")
        if script_path and os.path.exists(script_path):
            try:
                subprocess.Popen(["python", script_path])
            except Exception as e:
                logging.error(f"启动工具失败: {str(e)}")
                messagebox.showerror("错误", f"启动工具失败: {str(e)}")

class ToolLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("T-Tools")
        self.root.geometry("360x440")  # 增加窗口高度以适应更多的顶部间距
        self.root.resizable(False, False)
        
        # 设置窗口背景色
        self.root.configure(bg='#f0f0f0')
        
        try:
            # 检查配置文件是否存在
            if not os.path.exists("launcher_config.json"):
                logging.error("配置文件不存在")
                messagebox.showerror("错误", "找不到配置文件 launcher_config.json")
                return
                
            # 加载配置
            with open("launcher_config.json", "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except Exception as e:
            logging.error(f"加载配置文件失败: {str(e)}")
            messagebox.showerror("错误", f"加载配置文件失败: {str(e)}")
            return
            
        # 创建主框架并美化
        self.main_frame = ttk.Frame(root, style='Main.TFrame')
        self.main_frame.pack(expand=True, fill="both", padx=10, pady=10)  # 减小内边距
        
        # 创建标题
        title_font = font.Font(family='Microsoft YaHei UI', size=14, weight='bold')
        title_label = tk.Label(
            self.main_frame,
            text="T-Tools 工具箱",
            font=title_font,
            bg='#f0f0f0'
        )
        title_label.pack(pady=(0, 10))  # 减小标题下方的间距
        
        # 创建工具图标
        self.create_tool_icons()
        
        # 美化退出按钮
        style = ttk.Style()
        style.configure('Exit.TButton', 
                       font=('Microsoft YaHei UI', 9),
                       padding=5)
        self.exit_button = ttk.Button(
            root,
            text="退出",
            command=root.quit,
            style='Exit.TButton'
        )
        self.exit_button.pack(side="bottom", pady=10)  # 将按钮移到底部
        
        self.config_file = "launcher_config.json"
        
    def save_config(self):
        """保存工具配置，包括位置信息"""
        try:
            # 更新位置信息
            for i, icon in enumerate(self.main_frame.icons):
                for tool in self.config["tools"]:
                    if tool["name"] == icon.tool_info["name"]:
                        tool["position"] = icon.position
            
            # 保存到文件
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"保存配置失败: {str(e)}")

    def create_tool_icons(self):
        # 确保assets目录存在
        if not os.path.exists("assets"):
            os.makedirs("assets")
            
        placeholder_image = "assets/placeholder.png"
        # 如果placeholder.png不存在，创建一个
        if not os.path.exists(placeholder_image):
            img = Image.new('RGBA', (ICON_SIZE, ICON_SIZE), 'gray')
            img.save(placeholder_image)
            
        tools = self.config.get("tools", [])
        
        # 调整网格布局
        GRID_SIZE = 100
        TOP_PADDING = 40
        
        # 创建一个列表来存储所有图标
        self.main_frame.icons = []
        
        for i in range(9):
            row = i // 3
            col = i % 3
            x = col * GRID_SIZE + 25
            y = row * GRID_SIZE + TOP_PADDING
            
            if i < len(tools):
                tool = tools[i]
            else:
                tool = {
                    "name": "空白位置",
                    "icon": placeholder_image,
                    "tooltip": "此位置暂无工具"
                }
            
            try:
                # 创建图标时传入位置信息
                icon = ToolIcon(self.main_frame, tool, placeholder_image, position=i)
                icon.place(x=x, y=y)
                icon.name_label.place(x=x, y=y+70)
                self.main_frame.icons.append(icon)
            except Exception as e:
                logging.error(f"创建图标失败: {str(e)}")

def main():
    try:
        root = tk.Tk()
        app = ToolLauncher(root)
        root.mainloop()
    except Exception as e:
        logging.error(f"程序启动失败: {str(e)}")
        messagebox.showerror("错误", f"程序启动失败: {str(e)}")

if __name__ == "__main__":
    main() 