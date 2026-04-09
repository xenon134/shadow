import tkinter as tk
from PIL import ImageTk
import threading
import queue

class Viewer:
    def __init__(self):
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._run_tkinter, daemon=True)
        self.thread.start()

    def _run_tkinter(self):
        self.root = tk.Tk()
        self.root.title("Remote Desktop")
        self.label = tk.Label(self.root)
        self.label.pack()
        self.root.bind("<<NewImage>>", self._on_new_image)
        self.root.mainloop()

    def _on_new_image(self, event):
        try:
            img = self.queue.get_nowait()
            photo = ImageTk.PhotoImage(img)
            self.label.config(image=photo)
            self.label.image = photo  # Keep a reference to prevent garbage collection
        except queue.Empty:
            pass

    def update_image(self, img):
        self.queue.put(img)
        self.root.event_generate("<<NewImage>>", when="tail")

    def close(self):
        # To close the tkinter window from another thread, we can use after_idle
        if self.root:
            self.root.after_idle(self.root.quit)