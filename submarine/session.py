import time
from threading import Thread

from helpers.session import Session as ParentSession
from helpers.tube import Tube


class Session(ParentSession):

    def __init__(self, pk, cert, macaroon, port, close_socket_func, logger):
        super().__init__(pk, cert, macaroon, port, close_socket_func, logger)
        self.session_status = None
        self.logger = logger


    def register(self, target_pk):
        """
        Announce the submarine to the periscope node with its public key, and wait for acknowledgement.
        @param target_pk: The public key of the periscope node
        @return: When the handshake has been completed
        """
        self.target_pk = target_pk
        self.send_session_message(data=f'0:{self.pk}')
        receiver_thread = Thread(target=self.receiver)
        receiver_thread.start()

        # Wait for acknowledgement of session before continuing
        while True:
            if self.session_status == 'DENIED':
                return False
            elif self.session_status == 'ACTIVE':
                return True
            else:
                time.sleep(0.1)


    def create_tube(self, connection, port, hostname):
        """
        Creates a Tube object for packet management, and announce to the Periscope node that a new connection is desired.
        @param connection: The socket connection related to this Tube.
        @param port: The port, which is also the identifier of the Tube.
        @param hostname: The hostname related to the connection.
        """
        tube = Tube(port, self.local_socket_close, connection)
        self.tubes[port] = tube
        self.send_session_message(data=f'1:{port}:{hostname}')
        self.logger.log_inform(f'Created tube for {hostname}')

        #Thread(target=tube.pipe_packets_to_socket, args=(0,)).start()


    def receive_session_message(self, message):
        """
        Handle incoming session messages such as tube close creation etc.
        @param message: The session message in question.
        """
        # Continue parsing the message
        message = message.split(':', 1)
        m_type = int(message[0])
        m_content = message[1]

        switcher = {
            # Session status message
            0: lambda c: self.set_session_status(c),

            # Socket open message
            1: lambda c: print(c),

            # Socket close message
            2: lambda c: self.remote_socket_close(c),
        }

        switcher.get(m_type, lambda _: print('Invalid message type'))(m_content)


    def set_session_status(self, value):
        """
        Helper function related to the handshake
        @param value: The response of the Periscope related to the handshake
        """
        self.session_status = value
