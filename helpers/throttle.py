import threading
import queue
import time


class Throttle:
    def __init__(self, interval, function, transaction_queue, send_dummy=False, dummy=None):
        self.interval = interval
        self.function = function
        self.queue = transaction_queue
        self.send_dummy = send_dummy
        self.dummy = dummy
        self.e = threading.Event()
        self.t = threading.Thread(target=self.throttle)
        self.t.start()

    def throttle(self):
        while not self.e.wait(self.interval):
            if self.send_dummy:
                if self.queue.empty():
                    self.dummy = (str(time.time()).encode(), -1, -1)
                    arg = self.dummy
                else:
                    arg = self.queue.get()
            else:
                arg = self.queue.get()

            threading.Thread(target=self.function, args=arg).start()
