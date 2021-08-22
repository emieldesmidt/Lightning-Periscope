import base64
import codecs
import json
import os
import csv
import sys
import time

import grpc
from google.protobuf.json_format import MessageToJson

import router_pb2 as routerrpc
import router_pb2_grpc as routerstub
import rpc_pb2 as ln
import rpc_pb2_grpc as lnrpc
from helpers.crypt import Crypt
from helpers.logger import Logger

os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'


class Session:

    def __init__(self, pk, cert, macaroon, port, close_socket_func, logger: Logger):
        self.pk = pk
        self.target_pk = None

        cert = open(cert, 'rb').read()
        creds = grpc.ssl_channel_credentials(cert)
        channel = grpc.secure_channel(f'localhost:{port}', creds)
        self.stub = lnrpc.LightningStub(channel)
        self.routerstub = routerstub.RouterStub(channel)

        self.macaroon = codecs.encode(open(macaroon, 'rb').read(), 'hex')

        self.crypt = Crypt().crypt_pair_generator()
        self.tubes = {}

        self.close_socket = close_socket_func
        self.logger: Logger = logger

        self.total_cost = 0
        self.avg_latency = []

    def receiver(self):
        """
        The receiver method responsible for accepting and directing incoming lightning packets that carry data.
        Best to be started in a threaded way.
        """
        request = ln.InvoiceSubscription()

        for invoice in self.stub.SubscribeInvoices(request, metadata=[('macaroon', self.macaroon)]):

            # Try to retrieve message content, excepts as a KeyError if not a message (and ignores it)
            msg = json.loads(MessageToJson(invoice))
            try:
                payload = msg['htlcs'][0]['customRecords']['9780141036144']
            except KeyError:
                continue

            # Parse and split message
            payload_decoded = base64.b64decode(payload).decode('utf-8').split(':', 2)
            tube_idx = int(payload_decoded[0])
            packet_idx = int(payload_decoded[1])
            packet_content = base64.b64decode(payload_decoded[2][2:-1])

            # tube_idx of 0 indicates a service message
            if tube_idx == 0:
                service_message = str(packet_content)[2:-1]
                self.receive_session_message(service_message)
                continue

            # tube_idx of -1 indicates a dummy message used to hide traffic patterns, should be ignored
            if tube_idx == -1:
                diff = round(float(time.time()) - float(packet_content.decode()), 3)
                self.avg_latency.append(diff)
                print(f"{diff}")
                if len(self.avg_latency) == 2500:
                    with open("latencies.txt", 'a+') as file:
                        wr = csv.writer(file, quoting=csv.QUOTE_NONNUMERIC)
                        wr.writerow(self.avg_latency)
                        average = sum(self.avg_latency) / len(self.avg_latency)
                        print("Average of the list =", round(average, 2))
                continue

            # Direct packet to right tube
            try:
                t = self.tubes[int(tube_idx)]
                t.packet_queue[packet_idx] = packet_content

                source = f'{t.hostname}:{tube_idx}'
                self.logger.log_receive(f'{source}', f'Received {sys.getsizeof(packet_content)} bytes, packet index: {packet_idx}')

            except KeyError:
                self.logger.log_error(
                    f'Received {sys.getsizeof(packet_content)} bytes, but tube {tube_idx} is non-existing.')


    def send(self, data: bytes, packet_idx: int, tube_idx: int):
        """
        Send method: Sends a formatted packet with the data to the linked node.
        @param data: The data to be sent.
        @param packet_idx: The index that the packet should hold, required for reconstruction.
        @param tube_idx: The index of the tube, required for directing it to the right socket on the other side.
        """

        # The packet is attempted to be send across a non-existing tube that has likely been deleted
        if (int(tube_idx) not in self.tubes) and int(tube_idx) != 0 and int(tube_idx) != -1:
            return

        # Convert to base64 for safe transmission
        enc_data = base64.b64encode(data)

        # Packet: [tube_idx]:[packet_idx]:[packet_content]
        packet = f'{tube_idx}:{packet_idx}:{str(enc_data)}'.encode()

        # Crypt object is occasionally occupied, retry if necessary
        preimage = None
        phash = None
        while preimage is None or phash is None:
            try:
                preimage, phash = next(self.crypt)
            except ValueError:
                pass

        # Keysend record for invoice-free transaction, as well as the data carrying record
        custom_records = {
            5482373484: preimage,
            9780141036144: packet
        }

        # The request with the embedded custom records
        request = routerrpc.SendPaymentRequest(
            payment_hash=phash,
            amt=1,
            final_cltv_delta=40,
            dest=bytes.fromhex(self.target_pk),
            timeout_seconds=200,
            dest_custom_records=custom_records,
            fee_limit_sat=40,
            no_inflight_updates=True,
            dest_features=[9],
        )

        if int(tube_idx) == 0:
            dest = 'SUB'
        elif int(tube_idx) == -1:
            dest = 'DUMMY'
        else:
            dest = f'{self.tubes[int(tube_idx)].hostname}:{tube_idx}'

        # Update stream has to be consumed
        # Timeout after X seconds. Idea: Detect outliers automatically
        for update in self.routerstub.SendPaymentV2(request, metadata=[('macaroon', self.macaroon)]):

            # Check for failure
            msg = json.loads(MessageToJson(update))
            if 'fee' in msg:
                self.total_cost += int(msg['fee']) + int(msg['value'])
                self.logger.log_send(dest,
                                     f'[{round(self.total_cost * 0.00044336, 3)} Eur] {packet_idx} - Sending {sys.getsizeof(data)} bytes')

            if 'failureReason' in msg:
                self.logger.log_error(f"Transaction failed, reason: {msg['failureReason']}:{request}")

    def get_packet(self, tube_idx: int):
        return self.tubes[tube_idx].get_packet()

    def send_session_message(self, data: str):
        """
        Wrapper method of self.send for sending session related messages.
        @param data: The session message to be send.
        """
        self.send(data=data.encode(), packet_idx=0, tube_idx=0)


    def receive_session_message(self, message: str):
        """
        Handle incoming session messages.
        Function declaration to enforce implementation by the Periscope and Submarine Session classes.
        @param message: the message to be handled.
        """
        raise NotImplementedError


    def local_socket_close(self, tube_idx: int):
        """
        The socket has closed somewhere on this side, close and or delete all the related attributes and inform the peer.
        @param tube_idx: The index of the tube that is closing
        """
        try:
            self.logger.log_inform(f'Closing down the socket on {tube_idx} as the local connection closed')
            self.close_socket(tube_idx)
        except Exception as e:
            self.logger.log_error(e)
            return

        try:
            self.tubes[int(tube_idx)].piping = False
            del self.tubes[int(tube_idx)]

        except KeyError:
            self.logger.log_error(
                f'Could not remove {tube_idx} from {self.tubes.keys()}, maybe it was already removed elsewhere')


    def remote_socket_close(self, tube_idx: int):
        """
        The socket has closed on the other side, close and or delete all the related attributes.
        @param tube_idx: The index of the tube to be closed.
        """
        try:
            self.logger.log_inform(f'Closing down the socket on {tube_idx} as the remote connection closed')
            self.close_socket(tube_idx)
        except Exception as e:
            self.logger.log_error(e)
            return

        try:
            self.tubes[int(tube_idx)].piping = False
            del self.tubes[int(tube_idx)]
        except KeyError:
            self.logger.log_error(
                f'Could not remove {tube_idx} from {self.tubes.keys()}, maybe it was already removed elsewhere')
