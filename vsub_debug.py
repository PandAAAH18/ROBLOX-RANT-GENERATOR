import tkinter as tk
from tkinter import ttk, scrolledtext
import sys

print("DEBUG: Script starting...")
print(f"DEBUG: Python version: {sys.version}")

class VSubApp:
    def __init__(self, root):
        print("DEBUG: VSubApp __init__ called")
        self.root = root
        self.root.title("VSub TTS Generator - DEBUG")
        self.root.geometry("800x600")
        self.setup_ui()
        print("DEBUG: UI setup complete")
    
    def setup_ui(self):
        print("DEBUG: Setting up UI...")
        # Create a simple UI to test
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Simple label
        label = ttk.Label(main_frame, text="VSub TTS Generator")
        label.grid(row=0, column=0, pady=20)
        
        # Text input
        self.text_input = scrolledtext.ScrolledText(main_frame, width=60, height=10)
        self.text_input.grid(row=1, column=0, pady=10)
        self.text_input.insert("1.0", "Test text for TTS generation.")
        
        # Button
        btn = ttk.Button(main_frame, text="Test Button", command=self.test_button)
        btn.grid(row=2, column=0, pady=10)
        
        # Status
        self.status = ttk.Label(main_frame, text="Ready")
        self.status.grid(row=3, column=0, pady=10)
        
        print("DEBUG: UI elements created")
    
    def test_button(self):
        print("DEBUG: Button clicked!")
        self.status.config(text="Button was clicked!")
        print(f"DEBUG: Text content: {self.text_input.get('1.0', 'end-1c')}")

# Main execution with error handling
if __name__ == "__main__":
    try:
        print("DEBUG: Creating tkinter root window...")
        root = tk.Tk()
        print("DEBUG: Root window created")
        app = VSubApp(root)
        print("DEBUG: App instance created, starting mainloop...")
        root.mainloop()
        print("DEBUG: Mainloop ended")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")