__author__ = 'Taavi'

import threading
import logging

from packets import *
from socket import *


class PacketParser(threading.Thread):

    WAITING_PACKET_HEADER = 1
    COMBINING_HEADER = 2
    COMBINING_PACKET = 3

    def __init__(self, receive_socket):
        threading.Thread.__init__(self)

        self.receive_socket = receive_socket
        self.current_payload_length = 0
        self.current_header = 0
        self.current_payload_buffer = ''
        self.header_buffer = ''
        self.state = self.WAITING_PACKET_HEADER

        #Delegates
        self.on_packet_delegate = None
        self.on_connection_lost = None

        self.start()

    def run(self):
        while True:
            try:
                data = self.receive_socket.recv(2000)

                for item in data:
                    self.process_received_char(item)

            except error, exc:
                logging.info("Connection interrupted")
                if self.on_connection_lost is not None:
                    self.on_connection_lost()
                break

    def process_received_char(self, item):
        if self.state == self.WAITING_PACKET_HEADER:
            if item == P.PACKET_START:
                self.header_buffer += item
                self.state = self.COMBINING_HEADER

        elif self.state == self.COMBINING_HEADER:
            self.header_buffer += item
            if len(self.header_buffer) == 9:
                #logging.info("Found header, checking")

                if P.check_header(self.header_buffer):
                    #logging.info("Check succeeded")
                    self.current_header = int(self.header_buffer.split(P.HEADER_FIELD_SEPARATOR)[1])
                    self.current_payload_length = int(self.header_buffer.split(P.HEADER_FIELD_SEPARATOR)[2])

                    if self.current_payload_length == 0:
                        self.emit_packet(self.current_header, '')
                        self.state = self.WAITING_PACKET_HEADER
                    else:
                        self.state = self.COMBINING_PACKET
                else:
                    #logging.info("Check failed")
                    self.state = self.WAITING_PACKET_HEADER

                self.header_buffer = ''

        elif self.state == self.COMBINING_PACKET:
            self.current_payload_buffer += item

            if len(self.current_payload_buffer) == self.current_payload_length:
                #logging.info("Got a packet, header: (" + str(self.current_header) + \
                #             ") payload: (" + self.current_payload_buffer + ")")

                self.emit_packet(self.current_header, self.current_payload_buffer)

                self.current_payload_buffer = ''
                self.state = self.WAITING_PACKET_HEADER

    def sub_on_packet(self, func):
        self.on_packet_delegate = func

    def sub_on_connection_lost(self, func):
        self.on_connection_lost = func

    def try_parse_packet(self, header, payload):
        packet = None
        count = 0

        while packet is None or count < 2:
            if count == 0:
                packet = UpdateTextPacket.try_parse(header, payload)
            elif count == 1:
                packet = IntroductionPacket.try_parse(header, payload)
            count += 1

        return packet

    def emit_packet(self, header, payload):
        packet = self.try_parse_packet(header, payload)

        if packet is not None:
            if self.on_packet_delegate is not None:
                self.on_packet_delegate(packet)
        else:
            logging.info("Packet received but unknown")