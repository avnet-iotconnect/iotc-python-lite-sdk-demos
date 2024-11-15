import time
from threading import Timer

class infinite_timer:
    """A Timer class that does not stop, unless you want it to."""

    def __init__(self, seconds, target, arg = []):
        self._should_continue = False
        self.is_running = False
        self.seconds = seconds
        self.target = target
        self.arg = arg
        self.thread = None
    
    def _handle_target(self, arg):
        self.is_running = True
        self.target(arg)
        self.is_running = False
        #print('handled target :' + str(self.seconds))
        self._start_timer()
    
    def _start_timer(self):
        # Code could have been running when cancel was called.
        if self._should_continue:
            if self.thread is not None:
                self.thread.cancel()
                del(self.thread)
                self.thread = None
            self.thread = Timer(self.seconds, self._handle_target, self.arg)
            self.thread.daemon = True
            self.thread.name = "RTM"
            self.thread.start()
    
    def start(self):
        if not self._should_continue and not self.is_running:
            self._should_continue = True
            self._start_timer()
    
    def cancel(self):
        if self.thread is not None:
            # Just in case thread is running and cancel fails.
            self._should_continue = False
            self.is_running = False
            self.thread.cancel()
            del(self.thread)
            self.thread = None

