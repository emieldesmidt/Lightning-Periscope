import csv
import select
import socket
import sys
import queue
import time
from threading import Thread
from helpers.throttle import Throttle
from helpers.logger import Logger
from session import Session

LIMIT_LIST = ['mozilla', 'telemetry', 'staticcdn.duckduckgo', 'brxt.mendeley.com', 'profile.accounts.firefox.com',
              'api.accounts.firefox.com', 'easylist-downloads.adblockplus.org']


class Submarine:

    def __init__(self, submarine_node, periscope_pk, throttle_interval=(1/20), throttle_dummy=True):

        self.logger = Logger('SUB')

        # Set up session object
        # This will manage the socket channels as well as operational communication
        self.session = Session(submarine_node['pk'], submarine_node['cert'], submarine_node['mac'],
                               submarine_node['port'], self.close_socket,
                               self.logger)

        # Register at the periscope node, blocking until handshake completed
        self.logger.log_inform(f'Registering for a connection at {periscope_pk}')
        registered = self.session.register(periscope_pk)

        if not registered:
            sys.exit()
        self.logger.log_inform(f'Established connection with {periscope_pk}')

        # Create a TCP/IP socket
        self.server: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setblocking(False)

        # Bind the socket to the local port
        server_address = ('localhost', 8742)
        self.server.bind(server_address)
        self.logger.log_inform(f'Starting up on {server_address[0]}:{server_address[1]}')

        # Listen for incoming connections, buffer of ten
        self.server.listen(10)

        self.inputs = [self.server]
        self.outputs = []

        # Dictionary object to keep track of which sockets belong to which tube
        self.socket_tube_dict = {}

        # Start the throttle with the given parameters if desired
        self.t_queue = queue.Queue()
        Throttle(throttle_interval, self.session.send, self.t_queue, throttle_dummy, (b'0', -1, -1))

        self.server_loop()

    def server_loop(self):
        """
        The server loop of the Submarine, accepts new incoming connections from the client and redirects packets from existing connections to the right tube
        """
        while self.inputs:

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

                # The server socket is readable, indicating incoming connection
                if s is self.server:

                    # Handle the new connection attempt
                    self.new_connection_setup(s)

                # Existing socket receiving data
                else:

                    # Port number is used as unique tube identifier
                    try:
                        tube_idx = s.getpeername()[1]

                    except OSError as o:
                        self.logger.log_error(f'fatal error for: {s}, {o}')
                        continue

                    try:
                        # Receive buffers in chunks that are transmittable
                        data = s.recv(729)

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
                try:
                    tube_idx = s.getpeername()[1]
                except OSError as o:
                    if s in self.outputs:
                        self.outputs.remove(s)
                    if s in self.inputs:
                        self.inputs.remove(s)
                    continue

                data = self.session.get_packet(tube_idx)
                if data:
                    try:
                        s.sendall(data)
                    except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
                        self.logger.log_error(
                            f'Exception occurred on tube {tube_idx}, will close down socket and inform peer: {e}')

                        # Discard the socket locally and inform peer
                        Thread(target=self.session.local_socket_close, args=(tube_idx,)).start()
                        continue
                    self.logger.log_inform(f'Sending {sys.getsizeof(data)} to socket')

            for s in exceptional:
                self.inputs.remove(s)
                if s in self.outputs:
                    self.outputs.remove(s)
                s.close()

    def new_connection_setup(self, new_socket):
        """
        The socket is new, set up a tube.
        @param new_socket: The connection
        """
        # Accept local incoming connection
        connection, client_address = new_socket.accept()
        self.logger.log_inform(f'New local socket established on port {client_address[1]}')

        connection.setblocking(0)
        self.inputs.append(connection)
        self.outputs.append(connection)

        try:
            # Extract relevant details and set up tube
            hostname, port = self.new_connection_details(connection)
            self.session.create_tube(connection, port, hostname)
            self.socket_tube_dict[connection] = port

        except Exception as e:
            self.logger.log_error(f'Exception occurred during new connection setup: {e}')
            # self.inputs.remove(connection)
            connection.shutdown(1)
            connection.close()

    def close_socket(self, tube_idx):
        """
        Cleanup for the closing tube.
        @param tube_idx: tube identifier.
        """
        if tube_idx in self.socket_tube_dict.values():
            for s, idx in self.socket_tube_dict.items():
                if idx == tube_idx:
                    s.shutdown(1)
                    s.close()
                    self.inputs.remove(s)
                    self.outputs.remove(s)
                    del self.socket_tube_dict[s]
                    del s
                    self.logger.log_inform(f'Successfully closed socket on port {tube_idx}')
                    return
        else:
            raise Exception(f'The socket {tube_idx} has already been removed')

    def new_connection_details(self, connection):
        """
        Extract the relevant details out of the expected CONNECT message
        @param connection: The connection that will send an CONNECT
        @return: The hostname and the port.
        """
        port = connection.getpeername()[1]

        # Create a new socket with the port number as identifier
        conn = str(connection.recv(512))[2:-1]

        if conn is None or 'CONNECT ' not in conn:
            raise Exception(f'No CONNECT message received, not eligible for proxy: {conn}')

        hostname = conn.split(':', 1)[0].replace('CONNECT ', '')
        self.logger.log_inform(f'Establishing a tube to connect to {hostname}')

        # Check if this connection could become expensive
        if any(map(hostname.__contains__, LIMIT_LIST)):
            raise Exception(f'Connection to {hostname} for tube {port} blocked to limit traffic')

        return hostname, port


# Preload information of the involved nodes
nodes = {}
with open('../creds.txt') as credentials:
    csv_reader = csv.reader(credentials, delimiter=',')
    line_count = 0
    for row in csv_reader:
        nodes[row[0]] = {'cert': row[1], 'mac': row[2], 'pk': row[3], 'port': row[4]}

# Select the current node and extract the pk of the periscope node
node = nodes['carol']
target_pk = nodes['alice']['pk'] #"02b13dc721458c5d795d9ad5b9598d2399fe8e1c00251bdf1d21d16ff309e40178"

sub = Submarine(node, target_pk)
