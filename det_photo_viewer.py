#!/usr/bin/env python3
"""
DET Photo Viewer - Displays target image with a live 60-second countdown timer.
Used by 'det-drill' for Skill 8: Write About the Photo.
"""

import sys
import os
import time
import tempfile
import subprocess

def launch_fallback(image_path):
    try:
        if os.name == "nt" or sys.platform.startswith("win"):
            os.startfile(image_path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", image_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", image_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def main():
    if len(sys.argv) < 2:
        print("Usage: det-photo-viewer <image_path> [seconds] [title]")
        sys.exit(1)

    image_path = os.path.abspath(sys.argv[1])
    if not os.path.exists(image_path):
        print(f"Error: Image '{image_path}' not found.")
        sys.exit(1)

    total_seconds = 60
    if len(sys.argv) >= 3:
        try:
            total_seconds = int(sys.argv[2])
        except ValueError:
            pass

    title_text = sys.argv[3] if len(sys.argv) >= 4 else "Write About the Photo"

    # Attempt Tkinter GUI
    try:
        import tkinter as tk
        from PIL import Image
    except Exception:
        launch_fallback(image_path)
        sys.exit(0)

    try:
        root = tk.Tk()
    except Exception:
        launch_fallback(image_path)
        sys.exit(0)

    root.title(f"Duolingo English Test — {title_text}")
    root.configure(bg="#181825")

    # Load and scale image maintaining aspect ratio
    tmp_png_path = None
    try:
        pil_img = Image.open(image_path)
        max_w, max_h = 660, 420
        pil_img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            pil_img.save(tmp.name, "PNG")
            tmp_png_path = tmp.name

        tk_img = tk.PhotoImage(file=tmp_png_path)
    except Exception as e:
        if tmp_png_path and os.path.exists(tmp_png_path):
            os.unlink(tmp_png_path)
        root.destroy()
        launch_fallback(image_path)
        sys.exit(0)

    # UI Elements
    header_frame = tk.Frame(root, bg="#181825")
    header_frame.pack(fill="x", padx=20, pady=(15, 5))

    lbl_badge = tk.Label(
        header_frame,
        text="DUOLINGO ENGLISH TEST",
        font=("Helvetica", 10, "bold"),
        fg="#a6e3a1",
        bg="#181825"
    )
    lbl_badge.pack(anchor="w")

    lbl_instruction = tk.Label(
        header_frame,
        text="Write one or more sentences that describe the image.",
        font=("Helvetica", 14, "bold"),
        fg="#cdd6f4",
        bg="#181825"
    )
    lbl_instruction.pack(anchor="w", pady=(2, 8))

    # Timer display
    timer_frame = tk.Frame(header_frame, bg="#313244", padx=12, pady=4)
    timer_frame.pack(anchor="w")

    lbl_timer = tk.Label(
        timer_frame,
        text=f"⏱️ Tempo restante: {total_seconds // 60:02d}:{total_seconds % 60:02d}",
        font=("Helvetica", 13, "bold"),
        fg="#a6e3a1",
        bg="#313244"
    )
    lbl_timer.pack()

    # Image Container
    img_frame = tk.Frame(root, bg="#11111b", bd=2, relief="solid")
    img_frame.pack(padx=20, pady=10)

    lbl_image = tk.Label(img_frame, image=tk_img, bg="#11111b")
    lbl_image.image = tk_img
    lbl_image.pack(padx=6, pady=6)

    # Bottom helper bar
    footer_frame = tk.Frame(root, bg="#181825")
    footer_frame.pack(fill="x", padx=20, pady=(5, 15))

    lbl_footer = tk.Label(
        footer_frame,
        text="⌨️ Digite sua resposta no terminal  •  Pressione [ESC] para fechar a visualização",
        font=("Helvetica", 10),
        fg="#9399b2",
        bg="#181825"
    )
    lbl_footer.pack()

    # Window placement (center on screen)
    root.update_idletasks()
    win_w = root.winfo_reqwidth()
    win_h = root.winfo_reqheight()
    scr_w = root.winfo_screenwidth()
    scr_h = root.winfo_screenheight()
    pos_x = max(10, (scr_w - win_w) // 2)
    pos_y = max(10, (scr_h - win_h) // 2 - 30)
    root.geometry(f"+{pos_x}+{pos_y}")

    # Countdown loop
    remaining = [total_seconds]

    def update_timer():
        if remaining[0] > 0:
            remaining[0] -= 1
            m, s = divmod(remaining[0], 60)
            lbl_timer.config(text=f"⏱️ Tempo restante: {m:02d}:{s:02d}")
            if remaining[0] <= 10:
                lbl_timer.config(fg="#f38ba8")  # Red
            elif remaining[0] <= 25:
                lbl_timer.config(fg="#f9e2af")  # Amber
            root.after(1000, update_timer)
        else:
            lbl_timer.config(text="⏰ Tempo Esgotado! Conclua no terminal.", fg="#f38ba8")

    root.after(1000, update_timer)

    def close_app(event=None):
        try:
            root.destroy()
        except Exception:
            pass

    root.bind("<Escape>", close_app)
    root.bind("q", close_app)

    # Cleanup temp file on exit
    try:
        root.mainloop()
    finally:
        if tmp_png_path and os.path.exists(tmp_png_path):
            try:
                os.unlink(tmp_png_path)
            except Exception:
                pass

if __name__ == "__main__":
    main()
