
def sendSequence(receiver,sender,dataString):
    i = 0
    #get length of string
    strLen = len(dataString)
    sequence_length = 0
    if strLen%10 != 0:
        #if string is not a multiple of 50, create extra packet
        sequence_length=strLen/10 + 1
    else:
        sequence_length = strLen/10
    while i < sequence_length:
        buffer = dataString[i*10:(i+1)*10]
        packet = Packet.Packet(50,receiver,sender,0,1,ACK_REQUEST,list(buffer))
        sendPacket(packet)
        i = i+1
        pass
def sendFrame(toAddress,senderAddress,buff,ack):
        #turn off receiver to prevent reception while filling fifo
        setMode(RF69_MODE_STANDBY)
        #wait for modeReady
        #writeReg(REG_DIOMAPPING1,RF_DIOMAPPING1_DIO0_00)
        if len(buff) > 61:
                buff = buff[0:61]
        sentBuff=[len(buff)+2,toAddress,senderAddress,ack]+buff
        writeRegBurst(REG_FIFO,sentBuff)
        print("BUFFER_SIZE= "+str(len(buff)))
        setMode(RF69_MODE_TX)
        print("BUFFER SENT")
        startTime = time.time()
        DATASENT = False
        setMode(RF69_MODE_TX)
        while (not (readReg(REG_IRQFLAGS2) & RF_IRQFLAGS2_PACKETSENT)):
            pass
        setMode(RF69_MODE_STANDBY)




message="RPi.GPIO and spidev If you are using newer firmware youll need to get a newer spidev, the old one is no longer working:bashgit clone https://github.com/Gadgetoid/py-spidev cd py-spidev"

sendSequence(1,2,message)

'''data = "I'M GOING IN!"
packet = Packet.Packet(50,1,2,0,1,ACK_REQUEST,list(data))
sendPacket(packet)
receivedBuff = receiveTimeout(5000)
if not receivedBuff == 1:
    if ord(receivedBuff[5]) == ACK_REQUEST:
        packet = Packet.Packet(50,1,2,0,1,ACK_OK,list(data))
        sendPacket(packet)'''
