import select
import socket
import csv
import sys
import queue
import time
from threading import Thread

from session import Session
from helpers.logger import Logger
from helpers.throttle import Throttle


class Periscope:

    def __init__(self, node, throttle_interval=0.0, throttle_dummy=False):
        self.logger = Logger('PERI')

        # Sockets from which we expect to read or write
        self.inputs = []
        self.outputs = []

        # Dictionary object to keep track of which sockets belong to which tube
        self.socket_tube_dict = {}

        # Session object that interacts with the lightning protocol
        self.session = Session(node['pk'], node['cert'], node['mac'], node['port'], self.new_socket,
                               self.close_socket, self.logger)

        # Wait for a submarine registrant to appear
        self.logger.log_inform('Waiting for incoming connections')
        target_pk = self.session.activate()
        self.logger.log_inform(f'Established connection with {target_pk}')

        # Start the throttle with the given parameters if desired
        self.t_queue = queue.Queue()
        Throttle(throttle_interval, self.session.send, self.t_queue, throttle_dummy, (b'0', -1, -1))

        # Start the main server loop
        self.server_loop()

    def server_loop(self):
        """
        The server loop of the Periscope, listens on all the sockets for data to be transmitted over lightning to the Submarine
        """
        while True:

            # No sockets to be read, wait until there are
            while not self.inputs:
                time.sleep(0.1)

            # Purge closed sockets from the inputs
            self.inputs = [s for s in self.inputs if s.fileno() != -1]

            try:
                # Wait for at least one of the sockets to be ready for processing
                readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs, 1)
            except ValueError as v:
                # Purge closed sockets from the inputs
                self.inputs = [s for s in self.inputs if s.fileno() != -1]
                self.outputs = [s for s in self.outputs if s.fileno() != -1]
                continue

            # Handle inputs
            for s in readable:

                # Find the accompanying tube
                tube_idx = self.socket_tube_dict[s]

                try:
                    # Receive buffers in chunks that are transmittable
                    data = s.recv(850)

                except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
                    self.logger.log_error(
                        f'Exception occurred on tube {tube_idx}, will close down socket and inform peer: {e}')

                    # Discard the socket locally and inform peer
                    Thread(target=self.session.local_socket_close, args=(tube_idx,)).start()
                    continue

                # Send data through the tunnel
                assigned_index = self.session.tubes[tube_idx].assign_index()
                self.t_queue.put((data, assigned_index, tube_idx))

                if not data:
                    self.logger.log_inform(
                        f'Socket {tube_idx} concluded gracefully, will close down socket and inform peer')

                    # Discard the socket locally and inform the periscope node
                    self.close_socket(tube_idx)

            for s in writable:
                # Get the packet if it's there
                if s in self.socket_tube_dict:
                    data = self.session.get_packet(self.socket_tube_dict[s])
                    if data:
                        s.sendall(data)
                        self.logger.log_inform(f'Sending {sys.getsizeof(data)} to socket')

            for s in exceptional:
                self.inputs.remove(s)
                if s in self.outputs:
                    self.outputs.remove(s)
                s.close()

    def new_socket(self, port, hostname):
        """
        Activate a new socket. This method gets called by the session object, who just received a session message that a new socket is to be established
        @param port:
        @param hostname:
        """
        # If not already existing, create a new socket
        if port not in self.socket_tube_dict.values():
            # Setup a new connection to this host
            self.logger.log_inform(f'Trying to establish connection to {hostname}')
            sock = socket.create_connection((hostname, 443))
            self.logger.log_inform(f'Established connection to {hostname}')

            # Actively listen on the socket
            self.inputs.append(sock)
            self.outputs.append(sock)

            # Link socket to the tube object
            self.logger.log_inform(f'New socket-tube pair for port {port}')

            self.socket_tube_dict[sock] = port
            tube = self.session.tubes[int(port)]
            tube.set_connection(sock)
            tube.hostname = hostname

            # Send confirmation of established socket back
            self.t_queue.put((b'HTTP/1.1 200 Connection established\r\n\r\n', tube.assign_index(), port))

    def close_socket(self, tube_idx):
        """
        Cleanup for the closing tube.
        @param tube_idx: tube identifier.
        """
        if tube_idx in self.socket_tube_dict.values():
            for s, idx in self.socket_tube_dict.items():
                if idx == tube_idx:
                    self.logger.log_inform(f'Closing socket on port {tube_idx}')

                    s.shutdown(1)
                    s.close()
                    self.inputs.remove(s)
                    self.outputs.remove(s)
                    del self.socket_tube_dict[s]
                    del s
                    self.logger.log_inform(f'Successfully closed socket on port {tube_idx}')
                    return


# Preload information of the involved nodes
nodes = {}
with open('../creds.txt') as credentials:
    csv_reader = csv.reader(credentials, delimiter=',')
    line_count = 0
    for row in csv_reader:
        nodes[row[0]] = {'cert': row[1], 'mac': row[2], 'pk': row[3], 'port': row[4]}

# Select the current node
node = nodes['emiel']

peri = Periscope(node=node, )
