import time
from threading import Thread

from helpers.tube import Tube
from helpers.session import Session as ParentSession


class Session(ParentSession):

    def __init__(self, pk, cert, macaroon, port, new_socket_func, close_socket_func, logger):
        super().__init__(pk, cert, macaroon, port, close_socket_func, logger)

        self.target_pk = None
        self.new_socket = new_socket_func


    def activate(self):
        """
        Dummy method: Listen and perform a handshake with the periscope node before continuing
        """
        receiver_thread = Thread(target=self.receiver)
        receiver_thread.start()

        # Wait for acknowledgement of session before continuing
        while True:
            if self.target_pk is not None:
                return self.target_pk
            else:
                time.sleep(0.1)


    def receive_session_message(self, message: str):
        """
        Handler of incoming sesion messages, redirect it to the appropriate methods.
        @param message: the Session message in question
        """
        # Continue parsing the message
        message = message.split(':', 1)
        m_type = int(message[0])
        m_content = message[1]

        switcher = {
            # Session connection request
            0: lambda c: self.incoming_session_request(c),

            # Socket Tube announcement
            1: lambda c: self.incoming_socket_request(c),

            # Socket close message
            2: lambda c: self.remote_socket_close(c),
        }

        # Direct the message to the right handler, or default to logging it as invalid
        switcher.get(m_type, lambda _: self.logger.log_error(f'Invalid message type {m_type}'))(m_content)


    def incoming_socket_request(self, value):
        """
        The submarine has started a new connection, create a tube and setup a new socket
        @param value: Session message containing the port and hostname
        """
        port, hostname = value.split(':', 1)

        self.logger.log_inform(f'Created a new tube {port} for {hostname}')
        self.tubes[int(port)] = Tube(tube_idx=port, closing_func=self.local_socket_close)

        self.new_socket(int(port), hostname)


    def incoming_session_request(self, value):
        """
        Dummy handshake method to reply to a Submarine's session request
        @param value: The public key of the Submarine node
        """
        self.target_pk = value
        self.send_session_message('0:ACTIVE')
