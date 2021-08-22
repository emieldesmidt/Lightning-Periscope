import time
import socket


class Tube:

    def __init__(self, tube_idx, closing_func, connection: socket.socket = None, hostname: str = None):
        self.identifier = tube_idx
        self.packet_queue = {}
        self.connection = connection
        self.closing_func = closing_func
        self.hostname = hostname

        self.sending_index = 0
        self.pipe_thread = None
        self.piping = True

        self.receive_index = 0


    def set_connection(self, connection: socket.socket):
        """
        Helper method to link the connection to the tube
        """
        self.connection = connection


    def assign_index(self):
        """
        Helper method to set the right index to a packet going towards the peer node
        @return: the packet index
        """
        self.sending_index += 1
        return self.sending_index - 1


    def get_packet(self):
        packet = self.packet_queue.pop(self.receive_index, None)

        if packet:
            self.receive_index += 1

        return packet