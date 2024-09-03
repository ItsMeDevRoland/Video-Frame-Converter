import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import cv2
import os
from PIL import Image, ImageTk
import multiprocessing
import concurrent.futures
import threading
import queue
import time
import json

class SplashScreen(tk.Toplevel):
    def __init__(self, parent):
        tk.Toplevel.__init__(self, parent)
        self.title("Splash")
        self.geometry("300x200")
        self.overrideredirect(True)
        self.configure(bg="#4a90e2")
        
        label = tk.Label(self, text="MADE BY ItsMeDevRoland", font=("Segoe UI", 16, "bold"), fg="white", bg="#4a90e2")
        label.pack(expand=True)
        
        self.fade_in()
        self.center_on_screen()

    def fade_in(self):
        alpha = 0
        while alpha < 1:
            self.attributes("-alpha", alpha)
            alpha += 0.05
            self.update()
            time.sleep(0.05)

    def fade_out(self):
        alpha = 1
        while alpha > 0:
            self.attributes("-alpha", alpha)
            alpha -= 0.05
            self.update()
            time.sleep(0.05)
        self.destroy()

    def center_on_screen(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")

class VideoFrameConverter:
    def __init__(self, master):
        self.master = master
        self.master.withdraw()  # Hide the main window initially
        
        # Show splash screen
        self.splash = SplashScreen(master)
        self.master.after(3000, self.close_splash)  # Close splash after 3 seconds
        
        master.title("ItsMeDevRoland's Video Frame Converter")
        master.geometry("800x600")
        master.configure(bg="#f0f4f8")

        self.input_file = tk.StringVar()
        self.output_folder = tk.StringVar()
        self.image_format = tk.StringVar(value="jpg")
        self.quality = tk.IntVar(value=85)
        self.use_gpu = tk.BooleanVar(value=False)
        self.num_threads = tk.IntVar(value=multiprocessing.cpu_count())
        self.custom_name_pattern = tk.StringVar(value="frame_{:04d}")

        # New variables for additional settings
        self.use_opencl = tk.BooleanVar(value=False)
        self.use_tensorrt = tk.BooleanVar(value=False)
        self.enable_dev_features = tk.BooleanVar(value=False)  # New variable for TellProcess

        self.theme = tk.StringVar(value="light")

        self.load_settings()
        self.create_widgets()
        self.check_gpu()

        self.conversion_running = False
        self.conversion_thread = None
        self.frame_queue = queue.Queue(maxsize=100)

    def close_splash(self):
        self.splash.fade_out()
        self.master.deiconify()

    def create_widgets(self):
        style = ttk.Style()
        self.apply_theme(style)

        main_frame = ttk.Frame(self.master, padding="20 20 20 20", style='TFrame')
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.master.grid_columnconfigure(0, weight=1)
        self.master.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(main_frame, text="ItsMeDevRoland's Video Frame Converter", font=('Segoe UI', 16, 'bold'), foreground="#4a90e2").grid(row=0, column=0, columnspan=3, pady=20)

        ttk.Label(main_frame, text="Input File:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(main_frame, textvariable=self.input_file).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(main_frame, text="Browse", command=self.browse_input).grid(row=1, column=2, padx=5, pady=5)

        ttk.Label(main_frame, text="Output Folder:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(main_frame, textvariable=self.output_folder).grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(main_frame, text="Browse", command=self.browse_output).grid(row=2, column=2, padx=5, pady=5)

        ttk.Label(main_frame, text="Image Format:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        ttk.OptionMenu(main_frame, self.image_format, "jpg", "jpg", "png", "webp").grid(row=3, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(main_frame, text="Quality:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        quality_frame = ttk.Frame(main_frame)
        quality_frame.grid(row=4, column=1, sticky="ew", padx=5, pady=5)
        ttk.Scale(quality_frame, from_=1, to=100, orient=tk.HORIZONTAL, variable=self.quality, length=200, command=lambda _: self.quality.set(round(self.quality.get()))).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(quality_frame, textvariable=self.quality).pack(side=tk.LEFT, padx=(10, 0))

        self.gpu_checkbox = ttk.Checkbutton(main_frame, text="Use GPU (if available)", variable=self.use_gpu)
        self.gpu_checkbox.grid(row=5, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        ttk.Label(main_frame, text="Number of Threads:").grid(row=6, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(main_frame, textvariable=self.num_threads, width=5).grid(row=6, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(main_frame, text="Custom Name Pattern:").grid(row=7, column=0, sticky="w", padx=5, pady=5)
        pattern_entry = ttk.Entry(main_frame, textvariable=self.custom_name_pattern)
        pattern_entry.grid(row=7, column=1, sticky="ew", padx=5, pady=5)
        pattern_entry.bind("<Enter>", lambda event: self.show_tooltip(event, "Use {NameOfFile}_{: + paddingNumber + d} for Serializing and Telling the Program for the naming pattern"))
        pattern_entry.bind("<Leave>", self.hide_tooltip)

        # Add settings button
        ttk.Button(main_frame, text="Advanced Settings", command=self.show_settings).grid(row=8, column=0, columnspan=3, pady=10)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=9, column=0, columnspan=3, pady=20)
        self.convert_button = ttk.Button(button_frame, text="Convert", command=self.start_conversion, style='TButton')
        self.convert_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel_conversion, style='TButton')
        self.cancel_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button.config(state=tk.DISABLED)

        self.progress = ttk.Progressbar(main_frame, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.progress.grid(row=10, column=0, columnspan=3, pady=10, sticky="ew")

        self.status_label = ttk.Label(main_frame, text="")
        self.status_label.grid(row=11, column=0, columnspan=3, pady=5)

        # Add a console-like area for debugging
        self.console = tk.Text(main_frame, height=10, width=80, state=tk.DISABLED)
        self.console.grid(row=12, column=0, columnspan=3, pady=10, sticky="ew")

        # Add help link
        help_button = ttk.Button(main_frame, text="Help", command=self.show_help)
        help_button.grid(row=14, column=0, columnspan=3, pady=10)

    def show_settings(self):
        settings_window = tk.Toplevel(self.master)
        settings_window.title("Advanced Settings")
        settings_window.geometry("300x250")

        ttk.Checkbutton(settings_window, text="Use OpenCL (BETA)", variable=self.use_opencl).pack(pady=5)
        ttk.Checkbutton(settings_window, text="Use TensorRT (BETA)", variable=self.use_tensorrt).pack(pady=5)
        ttk.Checkbutton(settings_window, text="Enable Dev Features (TellProcess)", variable=self.enable_dev_features).pack(pady=5)

        ttk.Label(settings_window, text="Theme:").pack(pady=5)
        ttk.Radiobutton(settings_window, text="Light", variable=self.theme, value="light", command=lambda: self.apply_theme(ttk.Style())).pack(anchor=tk.W)
        ttk.Radiobutton(settings_window, text="Dark", variable=self.theme, value="dark", command=lambda: self.apply_theme(ttk.Style())).pack(anchor=tk.W)

        ttk.Label(settings_window, text="Warning: These options are in BETA.\nUse with caution.", font=('Segoe UI', 10, 'italic')).pack(pady=10)

    def browse_input(self):
        filename = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mov *.gif")])
        self.input_file.set(filename)

    def browse_output(self):
        folder = filedialog.askdirectory()
        self.output_folder.set(folder)

    def check_gpu(self):
        try:
            cv2.cuda.getCudaEnabledDeviceCount()
            self.use_gpu.set(True)
        except:
            self.use_gpu.set(False)
            self.gpu_checkbox.config(state='disabled')
            messagebox.showinfo("GPU Support", "Warning: CUDA is not available on this system. GPU acceleration will be disabled Automatically, For Your Convinience.")

    def process_frame(self, frame, frame_count, output_folder, image_format, quality):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(frame_rgb)
        output_path = os.path.join(output_folder, self.custom_name_pattern.get().format(frame_count) + f".{image_format}")
        pil_image.save(output_path, quality=quality)

    def extract_frames(self, input_path, use_gpu):
        cap = cv2.VideoCapture(input_path)
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_count = 0

        if use_gpu and cv2.cuda.getCudaEnabledDeviceCount() > 0:
            stream = cv2.cuda_Stream()
            while self.conversion_running and frame_count < self.total_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                gpu_frame = cv2.cuda_GpuMat()
                gpu_frame.upload(frame)
                self.frame_queue.put((gpu_frame.download(), frame_count))
                frame_count += 1
        else:
            while self.conversion_running and frame_count < self.total_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                self.frame_queue.put((frame, frame_count))
                frame_count += 1

        cap.release()
        self.frame_queue.put(None)  # Signal end of frames

    def convert_frames(self):
        output_folder = self.output_folder.get()
        image_format = self.image_format.get()
        quality = self.quality.get()

        while self.conversion_running:
            item = self.frame_queue.get()
            if item is None:
                break
            frame, frame_count = item
            self.process_frame(frame, frame_count, output_folder, image_format, quality)
            self.progress['value'] = (frame_count + 1) / self.total_frames * 100
            self.status_label.config(text=f"Processing frame {frame_count + 1} of {self.total_frames}")
            if self.enable_dev_features.get():
                self.log_to_console(f"Processed frame {frame_count + 1} of {self.total_frames}")
            self.master.update_idletasks()

        # Ensure progress bar reaches 100%
        self.progress['value'] = 100
        self.status_label.config(text="Conversion completed")
        if self.enable_dev_features.get():
            self.log_to_console("Conversion completed")
        self.master.update_idletasks()

    def start_conversion(self):
        input_path = self.input_file.get()
        output_folder = self.output_folder.get()
        use_gpu = self.use_gpu.get()
        num_threads = self.num_threads.get()

        if not input_path or not output_folder:
            messagebox.showerror("Error", "Please select input file and output folder.")
            return

        self.conversion_running = True
        self.convert_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)

        self.conversion_thread = threading.Thread(target=self.run_conversion, args=(input_path, output_folder, use_gpu, num_threads))
        self.conversion_thread.start()

    def run_conversion(self, input_path, output_folder, use_gpu, num_threads):
        try:
            extract_thread = threading.Thread(target=self.extract_frames, args=(input_path, use_gpu))
            extract_thread.start()

            with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(self.convert_frames) for _ in range(num_threads)]
                concurrent.futures.wait(futures)

            extract_thread.join()

            if self.conversion_running:
                self.master.after(0, lambda: messagebox.showinfo("Success", f"Converted {self.total_frames} frames."))
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("Error", f"An error occurred during conversion: {str(e)}"))
        finally:
            self.conversion_running = False
            self.master.after(0, self.reset_ui)

    def cancel_conversion(self):
        self.conversion_running = False
        self.status_label.config(text="Cancelling conversion...")

    def reset_ui(self):
        self.convert_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        self.progress['value'] = 0
        self.status_label.config(text="")

    def log_to_console(self, message):
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)

    def load_settings(self):
        appdata_path = os.getenv('APPDATA')
        settings_file = os.path.join(appdata_path, 'video_frame_converter_settings.txt')
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings = json.load(f)
                self.input_file.set(settings.get('input_file', ''))
                self.output_folder.set(settings.get('output_folder', ''))
                self.image_format.set(settings.get('image_format', 'jpg'))
                self.quality.set(settings.get('quality', 85))
                self.use_gpu.set(settings.get('use_gpu', False))
                self.num_threads.set(settings.get('num_threads', multiprocessing.cpu_count()))
                self.custom_name_pattern.set(settings.get('custom_name_pattern', 'frame_{:04d}'))
                self.use_opencl.set(settings.get('use_opencl', False))
                self.use_tensorrt.set(settings.get('use_tensorrt', False))
                self.enable_dev_features.set(settings.get('enable_dev_features', False))
                self.theme.set(settings.get('theme', 'light'))

    def save_settings(self):
        appdata_path = os.getenv('APPDATA')
        settings_file = os.path.join(appdata_path, 'ItsMeDevRoland_video_frame_converter_settings.txt')
        settings = {
            'input_file': self.input_file.get(),
            'output_folder': self.output_folder.get(),
            'image_format': self.image_format.get(),
            'quality': self.quality.get(),
            'use_gpu': self.use_gpu.get(),
            'num_threads': self.num_threads.get(),
            'custom_name_pattern': self.custom_name_pattern.get(),
            'use_opencl': self.use_opencl.get(),
            'use_tensorrt': self.use_tensorrt.get(),
            'enable_dev_features': self.enable_dev_features.get(),
            'theme': self.theme.get()
        }
        with open(settings_file, 'w') as f:
            json.dump(settings, f)

    def on_closing(self):
        self.save_settings()
        self.master.destroy()

    def show_tooltip(self, event, message):
        x, y, _, _ = self.master.bbox(event.widget)
        self.tooltip = tk.Toplevel(self.master)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.geometry(f"+{x+50}+{y+50}")
        label = tk.Label(self.tooltip, text=message, background="yellow", relief="solid", borderwidth=1)
        label.pack()

    def hide_tooltip(self, event):
        if hasattr(self, 'tooltip'):
            self.tooltip.destroy()

    def apply_theme(self, style):
        theme = self.theme.get()
    
        # Define light theme styles
        if theme == "light":
            style.theme_use('clam')
            style.configure('TButton', background="#4a90e2", foreground="white", font=('Segoe UI', 10), padding=10)
            style.configure('TLabel', background="#ffffff", foreground="#000000", font=('Segoe UI', 10))
            style.configure('TEntry', fieldbackground="#ffffff", foreground="#000000", insertbackground="#000000", font=('Segoe UI', 10))
            style.configure('TCheckbutton', background="#ffffff", foreground="#000000", font=('Segoe UI', 10))
        
            # Configure main window and all widgets
            self.master.configure(bg="#f0f4f8")
            self.update_widget_backgrounds("#f0f4f8")
        
        # Define dark theme styles
        elif theme == "dark":
            style.theme_use('clam')
            style.configure('TButton', background="#333333", foreground="white", font=('Segoe UI', 10), padding=10)
            style.configure('TLabel', background="#333333", foreground="white", font=('Segoe UI', 10))
            style.configure('TEntry', fieldbackground="#333333", foreground="white", insertbackground="white", font=('Segoe UI', 10))
            style.configure('TCheckbutton', background="#333333", foreground="white", font=('Segoe UI', 10))
        
            # Configure main window and all widgets
            self.master.configure(bg="#333333")
            self.update_widget_backgrounds("#333333")

    # Helper function to update widget backgrounds
    def update_widget_backgrounds(self, bg_color):
        for widget in self.master.winfo_children():
            # Update frame or widgets that need background color changes
            if isinstance(widget, (tk.Label, tk.Entry, tk.Checkbutton, tk.Frame, tk.LabelFrame)):
                widget.configure(bg=bg_color)
            # Recursively update children of frames
            if isinstance(widget, (tk.Frame, tk.LabelFrame)):
                for child in widget.winfo_children():
                    child.configure(bg=bg_color)



    def show_help(self):
        help_window = tk.Toplevel(self.master)
        help_window.title("Help")
        help_window.geometry("400x300")

        help_text = """
        Naming Pattern Help:
        - Use {NameOfFile}_{: + paddingNumber + d} for Serializing and Telling the Program for the naming pattern
        - For Example, 'frame_{:05d}' which results in frames that has frame_00001, frame_00002, and above
        - Feel free to Check the Source-Code to See how it works and if you have any good update for this naming pattern system
        """

        tk.Label(help_window, text=help_text, justify=tk.LEFT, font=('Segoe UI', 10)).pack(padx=20, pady=20)

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoFrameConverter(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
