#Packet() class
class Packet:
    def setNext(self,pkt):
        self.pkt = pkt
    def getNext(self):
        return self.pkt

    def __init__(self,length,receiver,sender,sequence_number,sequence_length,ack,buffer):
        self.length = length
        self.receiver = receiver
        self.sender = sender
        self.sequence_number = sequence_number
        self.sequence_length = sequence_length
        self.ack = ack
        self.buffer = buffer
        self.pkt = ""
