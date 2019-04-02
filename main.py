#Tower Server console script to control RFM69 Radio.
import Adafruit_GPIO.FT232H as FT232H
from RFM69registers import *
import requests
import time
import Packet
import json
# Temporarily disable FTDI serial drivers.
FT232H.use_FT232H()

# Find the first FT232H device.
ft232h = FT232H.FT232H()

# Create a SPI interface from the FT232H using ADUBUS3 as chip select.
# Use a clock speed of 500Khz, SPI mode 0, and most significant bit first.
spi = FT232H.SPI(ft232h, cs=3, max_speed_hz=500000, mode=0, bitorder=FT232H.MSBFIRST)

networkID=0x02
dataString =""
WEB_SERVER = "192.168.8.103"

CONFIG = {
  0x01: [REG_OPMODE, RF_OPMODE_SEQUENCER_ON | RF_OPMODE_LISTEN_OFF | RF_OPMODE_STANDBY],
  #no shaping
  0x02: [REG_DATAMODUL, RF_DATAMODUL_DATAMODE_PACKET | RF_DATAMODUL_MODULATIONTYPE_FSK | RF_DATAMODUL_MODULATIONSHAPING_00],
  #default:4.8 KBPS
  0x03: [REG_BITRATEMSB, RF_BITRATEMSB_55555],
  0x04: [REG_BITRATELSB, RF_BITRATELSB_55555],
  #default:5khz, (FDEV + BitRate/2 <= 500Khz)
  0x05: [REG_FDEVMSB, RF_FDEVMSB_50000],
  0x06: [REG_FDEVLSB, RF_FDEVLSB_50000],

  0x07: [REG_FRFMSB, RF_FRFMSB_433],
  0x08: [REG_FRFMID, RF_FRFMID_433],
  0x09: [REG_FRFLSB, RF_FRFLSB_433],

  # +13dBm formula: Pout=-18+OutputPower (with PA0 or PA1**)
  # +17dBm formula: Pout=-14+OutputPower (with PA1 and PA2)**
  # +20dBm formula: Pout=-11+OutputPower (with PA1 and PA2)** and high power PA settings (section 3.3.7 in datasheet)
  #0x11: [REG_PALEVEL, RF_PALEVEL_PA0_ON | RF_PALEVEL_PA1_OFF | RF_PALEVEL_PA2_OFF | RF_PALEVEL_OUTPUTPOWER_11111],
  #over current protection (default is 95mA)
  #0x13: [REG_OCP, RF_OCP_ON | RF_OCP_TRIM_95],

  # RXBW defaults are { REG_RXBW, RF_RXBW_DCCFREQ_010 | RF_RXBW_MANT_24 | RF_RXBW_EXP_5} (RxBw: 10.4khz)
  #//(BitRate < 2 * RxBw)
  0x19: [REG_RXBW, RF_RXBW_DCCFREQ_010 | RF_RXBW_MANT_16 | RF_RXBW_EXP_2],
  #for BR-19200: //* 0x19 */ { REG_RXBW, RF_RXBW_DCCFREQ_010 | RF_RXBW_MANT_24 | RF_RXBW_EXP_3 },
  #DIO0 is the only IRQ we're using
  0x25: [REG_DIOMAPPING1, RF_DIOMAPPING1_DIO0_01],

  0x28: [REG_IRQFLAGS2,RF_IRQFLAGS2_FIFOOVERRUN],
  #must be set to dBm = (-Sensitivity / 2) - default is 0xE4=228 so -114dBm
  0x29: [REG_RSSITHRESH, 220],
  #/* 0x2d */ { REG_PREAMBLELSB, RF_PREAMBLESIZE_LSB_VALUE } // default 3 preamble bytes 0xAAAAAA
  0x2e: [REG_SYNCCONFIG, RF_SYNC_ON | RF_SYNC_FIFOFILL_AUTO | RF_SYNC_SIZE_3 | RF_SYNC_TOL_0],
  #attempt to make this compatible with sync1 byte of RFM12B lib
  0x2f: [REG_SYNCVALUE1, 0x2D],
  #NETWORK ID
  0x30: [REG_SYNCVALUE2, 0x02],
  0x31: [REG_SYNCVALUE3, 0x54],
  0x37: [REG_PACKETCONFIG1, RF_PACKET1_FORMAT_VARIABLE | RF_PACKET1_DCFREE_OFF | RF_PACKET1_CRC_ON | RF_PACKET1_CRCAUTOCLEAR_ON | RF_PACKET1_ADRSFILTERING_OFF],
  #in variable length mode: the max frame size, not used in TX
  0x38: [REG_PAYLOADLENGTH, 66],
  #* 0x39 */ { REG_NODEADRS, nodeID }, //turned off because we're not using address filtering
  #TX on FIFO not empty
  0x3C: [REG_FIFOTHRESH, RF_FIFOTHRESH_TXSTART_FIFONOTEMPTY | RF_FIFOTHRESH_VALUE],
  #RXRESTARTDELAY must match transmitter PA ramp-down time (bitrate dependent)
  0x3d: [REG_PACKETCONFIG2, RF_PACKET2_RXRESTARTDELAY_2BITS | RF_PACKET2_AUTORXRESTART_ON | RF_PACKET2_AES_OFF],
  #for BR-19200: //* 0x3d */ { REG_PACKETCONFIG2, RF_PACKET2_RXRESTARTDELAY_NONE | RF_PACKET2_AUTORXRESTART_ON | RF_PACKET2_AES_OFF }, //RXRESTARTDELAY must match transmitter PA ramp-down time (bitrate dependent)
  #* 0x6F */ { REG_TESTDAGC, RF_DAGC_CONTINUOUS }, // run DAGC continuously in RX mode
  # run DAGC continuously in RX mode, recommended default for AfcLowBetaOn=0
  0x6F: [REG_TESTDAGC, RF_DAGC_IMPROVED_LOWBETA0],
  0x00: [255, 0]
}

#packet transmission control functions.

#change device mode in radio module.
def setMode(newMode):
        if newMode == RF69_MODE_TX:
                writeReg(REG_OPMODE, (readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_TRANSMITTER)
                #print("MODE_TX")
        elif newMode == RF69_MODE_RX:
                writeReg(REG_OPMODE, (readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_RECEIVER)
                #print("MODE_RX")
        elif newMode == RF69_MODE_SYNTH:
                writeReg(REG_OPMODE, (readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_SYNTHESIZER)
                print("MODE_SYNTH")
        elif newMode == RF69_MODE_STANDBY:
                writeReg(REG_OPMODE, (readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_STANDBY)
                #print("MODE_STANDBY")
        elif newMode == RF69_MODE_SLEEP:
                writeReg(REG_OPMODE, (readReg(REG_OPMODE) & 0xE3) | RF_OPMODE_SLEEP)
                print("MODE_SLEEP")
        while ((readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY)==0X00):
                pass
#read registry.
def readReg(reg):
        response = spi.transfer([reg,0x00])
        #print("registry "+str(reg)+" value "+str(int(response[1])))
        return response[1]
#write registry.
def writeReg(reg,val):
        addr=reg|0x80
        response=spi.transfer([addr,val])
#write data to reg burst.
def writeRegBurst(reg,buff):
        addr=reg|0x80
        response=spi.transfer([addr]+buff)
#send packet.
def sendPacket(packet):
    ack = packet.ack
    while True:
        #turn off receiver to prevent reception while filling fifo.
        setMode(RF69_MODE_STANDBY)
        #wait for modeReady
        #writeReg(REG_DIOMAPPING1,RF_DIOMAPPING1_DIO0_00).
        sendBuff=[packet.length,packet.receiver,packet.sender,packet.sequence_number,packet.sequence_length,packet.ack]+packet.buffer
        #fill FIFO.
        writeRegBurst(REG_FIFO,sendBuff)
        #Start transmitting.
        setMode(RF69_MODE_TX)
        #wait for packet transmitting complete.
        while (not (readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PACKETSENT)):
            pass
        print("SENDING PACKET: INDEX "+str(packet.sequence_number))
        if ack == ACK_OK:
            break
        pkt= receiveTimeout(300)
        if pkt =="-1":
            print("WAITING FOR ACK...")
        else:
            print("RESPONSE:"+str(pkt.ack))
            if pkt.ack == ACK_OK:
                print("ACK OK.")
                break
        pass
    setMode(RF69_MODE_STANDBY)
#send ack.
def sendAck(receiver,sender):
    packet = Packet.Packet(9,receiver,sender,0,1,ACK_OK,[])
    sendPacket(packet)
    print("SENT ACK.")

#write configuration to RFM69 to initilize device.
print("")
print("____________________________")
print("*** BRIZO CONTROL CENTER ***")
print("")
print("NETWORK MONITER CONSOLE")
print("")
print("INITIALIZING...")
for value in CONFIG.values():
        writeReg(value[0], value[1])
# Wait for ModeReady
while (readReg(REG_IRQFLAGS1) & RF_IRQFLAGS1_MODEREADY) == 0x00:
        pass
setMode(RF69_MODE_STANDBY)
print("NETWORK DEVICE READY.")




#data transmission functions.
ACK_OK = 128
ACK_REQUEST = 64
ACK_SEQUENCE_OK = 32

#send sequence of data.
def sendSequence(receiver,sender,dataString):
    i = 0
    #get length of string
    strLen = len(dataString)
    print("SENDING STRING SIZE "+str(strLen))
    print("SENDING STRING"+dataString)
    sequence_length = 0
    if strLen % 50 != 0:
        #if string is not a multiple of 50, create extra packet.
        sequence_length=strLen/50 + 1
    else:
        sequence_length = strLen/50

    print("TOTEL PACKETS TO SEND "+str(sequence_length))
    while i < sequence_length:
        buffer = dataString[i*50:(i+1)*50]
        print("SENDING BUFFER:"+buffer)
        packet = Packet.Packet(len(buffer)+7,receiver,sender,i,sequence_length,ACK_REQUEST,list(buffer))
        sendPacket(packet)
        i = i+1
        pass

#receive pakets with no time out.
'''def receiveFrame():
        if readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY:
                writeReg(REG_PACKETCONFIG2,(readReg(REG_PACKETCONFIG2) & 0xFB) or RF_PACKET2_RXRESTART)
        setMode(RF69_MODE_RX)
        while not (readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY):
                pass
        receivedBuff=""
        while readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_FIFONOTEMPTY:
                receivedBuff=receivedBuff+chr(readReg(REG_FIFO))
        return receivedBuff
'''
#receive pakets with timeout.
#timeout in miliseconds.
def receiveTimeout(timeout):
    #start timer
    startime = time.time()
    #Check and clear FIFO buffer before start receiving.
    if readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY:
        writeReg(REG_PACKETCONFIG2,(readReg(REG_PACKETCONFIG2) & 0xFB) or RF_PACKET2_RXRESTART)
    #Start receiving.
    setMode(RF69_MODE_RX)
    #wait
    while not (readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PAYLOADREADY):
        timeDiff = (time.time() - startime) * 1000
        if timeDiff > timeout:
            return "-1"
        time.sleep(0.05)
        pass
    receivedBuff=""
    while readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_FIFONOTEMPTY:
        receivedBuff=receivedBuff+chr(readReg(REG_FIFO))
    packet = Packet.Packet(ord(receivedBuff[0]),ord(receivedBuff[1]),ord(receivedBuff[2]),ord(receivedBuff[3]),ord(receivedBuff[4]),ord(receivedBuff[5]),receivedBuff[6:ord(receivedBuff[0])-1])
    return packet
    #sendPacket(packet)
def receiveSequence():
    receivedSequence = ""
    now = Packet.Packet(0,0,0,0,0,0,"")
    sequence_number = 0
    while  True:
        packet = receiveTimeout(1000)
        if packet == "-1":
            continue
        print("RECEIVED PACKET INDEX "+str(packet.sequence_number))
        if sequence_number == packet.sequence_number:
            if receivedSequence == "":
                receivedSequence = packet
            else :
                receivedSequence.setNext(packet)
            sequence_number = sequence_number +1
            now = packet
            sendAck(packet.receiver,packet.sender)
            #print("NOW 1 "+str(now.sequence_number))

        else :
            sendAck(packet.receiver,packet.sender)
            #print("NOW 2 "+str(now.sequence_number))
        if now.sequence_number == now.sequence_length -1:
            print("BREAKED/RECEIVING COMPLETE.")
            break
        pass
    return receivedSequence
#test functions.
while True :
    #dataString=raw_input("Enter message:")
    #sendSequence(2,1,dataString)
    print("LISTENING FROM BOAT ROUTING DEVICES.")
    print(time.ctime())
    dataString = ""
    head = ""
    now = ""
    head = receiveSequence()
    now = head
    while now != "":
        print("RECEIVING PACKET SEQUENCE.")
        dataString = dataString + now.buffer
        now = now.getNext()
    print("RECEIVED REQUEST:"+dataString)
    print("SENDING REQUEST TO WEB SERVER...")
    r = requests.post("http://"+WEB_SERVER+"/Project/io/android.php",data = {'data':dataString})
    print("RESPONSE:"+str(r.text))
    if len(r.text)<3000:
        print("SENDING RESPONSE TO BOAT.")
        sendSequence(2,1,str(r.text))
        #print(str(r.text[r.text.find("{"):]))
        dataString = ""
        r = ""

    pass
