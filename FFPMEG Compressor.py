import subprocess
import tkinter as tk
from tkinter import filedialog
from imageio_ffmpeg import get_ffmpeg_exe
import os


class App:
    def __init__(self, master):
        self.master = master
        master.title("ClipShrinker")

        self.input_file_label = tk.Label(master, text="Input File:")
        self.input_file_label.grid(row=0, column=0)

        self.input_file_path = tk.StringVar()
        self.input_file_path.set("No file selected")
        self.input_file_path_label = tk.Label(master, textvariable=self.input_file_path)
        self.input_file_path_label.grid(row=0, column=1)

        self.output_file_label = tk.Label(master, text="Output File:")
        self.output_file_label.grid(row=1, column=0)

        self.output_file_path = tk.StringVar()
        self.output_file_path.set("No file selected")
        self.output_file_path_label = tk.Label(master, textvariable=self.output_file_path)
        self.output_file_path_label.grid(row=1, column=1)

        self.select_input_button = tk.Button(master, text="Select Input File", command=self.select_input_file)
        self.select_input_button.grid(row=0, column=2)

        self.select_output_button = tk.Button(master, text="Select Output File", command=self.select_output_file)
        self.select_output_button.grid(row=1, column=2)

        self.render_button = tk.Button(master, text="Render", command=self.render)
        self.render_button.grid(row=2, column=1)

    def select_input_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("MP4 files", "*.mp4")])
        if file_path:
            self.input_file_path.set(file_path)

            # Automatically set the output file path based on the input file name
            output_file_path = os.path.splitext(file_path)[0] + "_opt.mp4"
            self.output_file_path.set(output_file_path)


    def select_output_file(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".mp4")
        if file_path:
            if os.path.exists(file_path):
                result = tk.messagebox.askyesno("File exists", "The file already exists. Do you want to overwrite it?")
                if not result:
                    return

            self.output_file_path.set(file_path)


    
    
    def render(self):
        input_file = self.input_file_path.get()
        output_file = self.output_file_path.get()

        # Get the path to the FFmpeg binary
        ffmpeg_path = get_ffmpeg_exe()

        # FFmpeg command to compress the video
        command = [
        ffmpeg_path,
        "-i", input_file,
        "-y",
        "-fs", "7950000",
        "-r", "60",
        "-s", "1280x720",
        "-b:a", "96000",
        "-b:v", "4000000",
        output_file
        ]

        if not input_file or not output_file or input_file == "No file selected" or output_file == "No file selected":
            tk.messagebox.showwarning("Warning", "Please select both input and output files.")
            return

        # Add the -y option to automatically overwrite output files without prompting the user
        process = subprocess.run(command, capture_output=True, text=True)
        if process.returncode == 0:
            tk.messagebox.showinfo("Rendering complete", "The video has been successfully rendered.")
            self.input_file_path.set("No file selected")
            self.output_file_path.set("No file selected")
        else:
            error_message = process.stderr or "An unknown error occurred."
            tk.messagebox.showerror("Error", f"An error occurred during rendering:\n{error_message}")



root = tk.Tk()
app = App(root)
root.mainloop()
