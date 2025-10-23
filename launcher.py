import PySimpleGUI as sg
import subprocess
import sys
import threading
import queue
import os
from datetime import datetime

# Define buttons and corresponding scripts
SCRIPTS = [
    ("Run Natural Hazard Updater", "NaturalHazardUpdaterTool.py"),
    ("Run Backup Hazard Data", "BackupHazardData.py"),
    ("Run Identify Feature Deletes", "IdentifyFeatureDeletes.py"),
    # Add more if needed
]

def stream_reader(pipe, q):
    for line in iter(pipe.readline, b''):
        q.put(line.decode(errors="ignore"))
    pipe.close()

def run_script(script_path, window):
    window["-OUT-"].update("")  # Clear output
    window["-STATUS-"].update(f"Running: {script_path}")
    python_exe = sys.executable
    cmd = [python_exe, script_path]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=os.getcwd()
        )
    except FileNotFoundError:
        window["-OUT-"].print(f"Script not found: {script_path}")
        return

    q = queue.Queue()
    threading.Thread(target=stream_reader, args=(proc.stdout, q), daemon=True).start()

    while True:
        event, _ = window.read(timeout=100)
        if event in (sg.WINDOW_CLOSED, "Exit"):
            try:
                proc.terminate()
            except Exception:
                pass
            break

        try:
            line = q.get_nowait()
            window["-OUT-"].print(line, end="")
        except queue.Empty:
            pass

        if proc.poll() is not None and q.empty():
            rc = proc.returncode
            window["-OUT-"].print(f"\n=== Finished with exit code {rc} ===")
            break

    window["-STATUS-"].update("Idle")

def main():
    sg.theme("DarkGrey5")  # Pick a theme or customize

    script_buttons = [
        [sg.Button(label, key=f"RUN::{path}", expand_x=True)]
        for label, path in SCRIPTS
    ]

    layout = [
        [sg.Text("Hazard Data Updater", font=("Helvetica", 14), expand_x=True)],
        [sg.Text("Status:"), sg.Text("Idle", key="-STATUS-", size=(40, 1))],
        *script_buttons,
        [sg.Button("Exit"), sg.Button("Open Logs", key="-OPENLOG-")],
        [sg.Multiline(size=(100, 25), key="-OUT-", autoscroll=True, write_only=True, reroute_stdout=False)],
    ]

    window = sg.Window("Hazard Launcher", layout, finalize=True)

    os.makedirs("logs", exist_ok=True)

    while True:
        event, _ = window.read()
        if event in (sg.WINDOW_CLOSED, "Exit"):
            break
        elif event == "-OPENLOG-":
            if os.name == "nt":
                os.startfile("logs")
            elif sys.platform == "darwin":
                subprocess.run(["open", "logs"])
            else:
                subprocess.run(["xdg-open", "logs"])
        elif event.startswith("RUN::"):
            _, script = event.split("::", 1)
            window["-OUT-"].print(f"\n=== Running {script} ===\n")
            run_script(script, window)

    window.close()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
