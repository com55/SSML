"""Single instance lock to prevent multiple instances of the application."""
import sys
import ctypes
from ctypes import wintypes
from types import TracebackType


# Windows API constants
MUTEX_ALL_ACCESS = 0x1F0001
ERROR_ALREADY_EXISTS = 183


class SingleInstanceLock:
    """
    Ensures only one instance of the application runs at a time using a Windows mutex.
    """
    
    def __init__(self, name: str = "StellaSoraModLauncher_SingleInstance"):
        self.name = name
        self.mutex_handle = None
        self._acquired = False
    
    def acquire(self) -> bool:
        """
        Try to acquire the single instance lock.
        
        Returns:
            True if this is the first instance, False if another instance exists
        """
        if sys.platform != "win32":
            # Non-Windows platforms - always allow
            return True
        
        try:
            # Try to create a named mutex
            kernel32 = ctypes.windll.kernel32
            
            self.mutex_handle = kernel32.CreateMutexW(
                None,  # default security attributes
                True,  # initially owned
                self.name  # mutex name
            )
            
            last_error = kernel32.GetLastError()
            
            if last_error == ERROR_ALREADY_EXISTS:
                # Another instance is already running
                if self.mutex_handle:
                    kernel32.CloseHandle(self.mutex_handle)
                    self.mutex_handle = None
                return False
            
            self._acquired = True
            return True
            
        except Exception:
            # If we can't create mutex, allow the instance to run
            return True
    
    def release(self) -> None:
        """Release the single instance lock."""
        if self.mutex_handle and sys.platform == "win32":
            try:
                kernel32 = ctypes.windll.kernel32
                kernel32.ReleaseMutex(self.mutex_handle)
                kernel32.CloseHandle(self.mutex_handle)
            except Exception:
                pass
            finally:
                self.mutex_handle = None
                self._acquired = False
    
    def __enter__(self):
        self.acquire()
        return self
    
    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> bool:
        self.release()
        return False


def find_and_focus_existing_window(window_title: str = "Stella Sora Mod Launcher") -> bool:
    """
    Find an existing window with the given title and bring it to foreground.
    
    Returns:
        True if window was found and focused, False otherwise
    """
    if sys.platform != "win32":
        return False
    
    try:
        user32 = ctypes.windll.user32
        
        # Find window by title
        hwnd = user32.FindWindowW(None, window_title)
        
        if hwnd:
            # Restore if minimized
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
            
            # Bring to foreground
            user32.SetForegroundWindow(hwnd)
            return True
        
        return False
        
    except Exception:
        return False
