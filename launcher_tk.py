import tkinter as tk
from tkinter import scrolledtext, messagebox
import subprocess
import threading
import queue
import os
import sys
from datetime import datetime

SCRIPTS = [
    ("Run Natural Hazard Updater", "NaturalHazardUpdaterTool.py"),
    ("Run Backup Hazard Data", "BackupHazardData.py"),
    ("Run Identify Feature Deletes", "IdentifyFeatureDeletes.py"),
]

def run_script(script_path, output_box, status_label):
    output_box.config(state='normal')
    output_box.delete(1.0, tk.END)

    script_name = os.path.splitext(os.path.basename(script_path))[0]
    log_file = os.path.join("logs", f"{script_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    status_label.config(text=f"Running: {script_name}", fg="green")
    python_exe = sys.executable
    cmd = [python_exe, script_path]

    q = queue.Queue()

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=os.getcwd(),
            text=True,           # decode output
            bufsize=1            # line buffered
        )
    except FileNotFoundError:
        output_box.insert(tk.END, f"❌ Script not found: {script_path}\n")
        status_label.config(text="Idle", fg="blue")
        return

    log_lines = []

    def enqueue_output():
        for line in proc.stdout:
            q.put(line)
            log_lines.append(line)
        proc.stdout.close()

    threading.Thread(target=enqueue_output, daemon=True).start()

    def poll_output():
        while not q.empty():
            line = q.get_nowait()
            output_box.insert(tk.END, line)
            output_box.see(tk.END)

        if proc.poll() is None:
            root.after(100, poll_output)
        else:
            while not q.empty():
                line = q.get_nowait()
                output_box.insert(tk.END, line)
                output_box.see(tk.END)
                log_lines.append(line)

            output_box.insert(tk.END, f"\n✅ Finished with exit code {proc.returncode}\n")
            status_label.config(text="Idle", fg="blue")

            # Save log
            try:
                with open(log_file, "w", encoding="utf-8") as f:
                    f.writelines(log_lines)
                output_box.insert(tk.END, f"\n📁 Log saved to {log_file}\n")
            except Exception as e:
                output_box.insert(tk.END, f"\n⚠️ Failed to save log: {e}\n")

    poll_output()

def open_logs_folder():
    try:
        os.makedirs("logs", exist_ok=True)
        if os.name == 'nt':
            os.startfile("logs")
        elif sys.platform == "darwin":
            subprocess.run(["open", "logs"])
        else:
            subprocess.run(["xdg-open", "logs"])
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open logs folder:\n{e}")

def build_ui():
    global root
    root = tk.Tk()
    root.title("Hazard Tools Launcher")
    root.geometry("850x600")

    tk.Label(root, text="Hazard Data Updater", font=("Helvetica", 16, "bold")).pack(pady=10)

    # Status label
    status_frame = tk.Frame(root)
    status_frame.pack()
    tk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
    status_label = tk.Label(status_frame, text="Idle", fg="blue")
    status_label.pack(side=tk.LEFT)

    # Buttons
    button_frame = tk.Frame(root)
    button_frame.pack(pady=10)

    for label, script in SCRIPTS:
        tk.Button(
            button_frame,
            text=label,
            width=40,
            command=lambda s=script: run_script(s, output_box, status_label)
        ).pack(pady=4)

    # Control buttons
    control_frame = tk.Frame(root)
    control_frame.pack(pady=5)
    tk.Button(control_frame, text="Open Logs", command=open_logs_folder).pack(side=tk.LEFT, padx=10)
    tk.Button(control_frame, text="Exit", command=root.quit).pack(side=tk.LEFT, padx=10)

    # Output log display
    global output_box
    output_box = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=20)
    output_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    return root

if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    app = build_ui()
    app.mainloop()
