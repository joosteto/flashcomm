#!/usr/bin/python3
import argparse
import configparser
import time

debug=False
verbose=False

try:
    import RPi.GPIO as GPIO
    import spidev
except ModuleNotFoundError:
    print("No RPi.GPIO or spidev module found, running in simulation mode")
    class spidev:
        class SpiDev:
            def __init__(self):
                pass
            def open(self, bus, device):
                self.bus=bus
                self.device=device
            def xfer2(self,data):
                return bytes([i%256 for i in [0,0]+list(range(len(data)))])
    class GPIO:
        def __init(self):
            pass
        def setmode(i):
            pass
        def setup(i,j):
            pass
        def output(i,j):
            pass


        
class flashcomm:
    def __init__(self, device=0, bus=0, max_speed_hz=None, ss=None, set_high=-1, set_low=-1):
        #data about flash chip. Should be infered from device id
        self.flashType="UNKNOWN"
        self.pagelength=256
        self.subsectorlength=None
        self.sectorlength=64*1024   #bytes
        
        self.flashbits=32*1024*1024

        #SPI location
        self.bus=0
        self.device=device
        self.spi=spidev.SpiDev()
        self.spi.open(self.bus, self.device)
        self.spi.max_speed_hz=max_speed_hz
        self.ss=ss
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.ss, GPIO.OUT)
        GPIO.output(self.ss, 1)

        if set_high>=0:
            GPIO.setup(set_high, GPIO.OUT)
            GPIO.output(set_high, 1)
            time.sleep(0.1)
        if set_low>=0:
            GPIO.setup(set_low, GPIO.OUT)
            GPIO.output(set_low, 0)
            time.sleep(0.1)

        self.detectFlashType()
        
    def __del__(self):
        GPIO.cleanup()
        

        
        
        
    def send_cmd(self, cmd, address=None, data=None):
        """
        send_cmd: send command to Flash Device (over SPI)
        Arguments:
          cmd: command to send (integer)
          address: None, or address to send after command
          data: bytes to send after cmd+address (type: bytes)
        Return: data returend by Flash. 
        """
        GPIO.output(self.ss, 0)
        if address is None:
            abytes=bytes([])
        else:
            abytes=address.to_bytes(3, 'little')
        if data is None:
            data=bytes([])
        cmdata=bytes([cmd])+abytes+data
        if debug:
            print(f'send_cmd: {hexstr(cmdata[:16])}')
        answ=self.spi.xfer2(cmdata)
        if debug:
            print(f'       -> {hexstr(answ[:16])}')
        GPIO.output(self.ss, 1)
        return answ
    
    def detectFlashType(self):
        id=self.read_id()
        if id['ManufacturerID'][0]==0x20:
            if id['MemoryType'][0]==0x20:
                self.flashType="M25P"
                #M25P10A: 
                #  1Mb flash bits, and reports MemoryCapacity=0x11)
                #  256 pagelength
                #  256 Kb sector (bits)
                self.sectorlength=256//8*1024  #in bytes
            
            elif id['MemoryType'][0]==0xba:
                self.flashType="N25Q"
                self.subsectorlength=4*1024            
                self.sectorlength=64*1024 #bytes
                #self.flashbits=32*1024*1024
                #N25Q032A: 32Mb flash bits, reports MemoryCapacity=0x16
            else:
                print(f"Warning: unknown memory type 0x{id['MemoryType'][0]:02x} for ManufacturerID=0x{id['ManufacturerID'][0]:02x}")
        elif id['ManufacturerID'][0]==0x9d:
            #IS25LP064D: memoryCapacity=0x17, flashbits=64Mb
            self.sectorlength=4*1024 #bytes
            self.flashType="IS25L" 
            
        else:
            print(f"WARNING: unknown flash type: 0x{id['ManufacturerID'][0]:02x}")
            
        self.flashbits=1<<(id['MemoryCapacity'][0]+3)  
        print(f'Detected {self.flashType} flash type, with a capacity of {self.flashbits} bits, {self.flashbits/1024/1024} Mb, or {self.flashbits/1024/1024/8} MByte')
        
    def write_enable(self):
        return self.send_cmd(0x06)


    def check_write_busy(self):
        """Return:
            True: Busy
            False: Ready
        """
        #Note: xc3sprog uses cmd read flag status (cmd=0x70), and checks for bit 7 (0x80)
        if self.flashType in ("M25P", "IS25L"):
            return (self.read_statusregister() & 0x01)!=0
        elif self.flashType=="N25Q":
            return (self.read_flagstatusregister() & 0x80)==0
    
    def wait_write_idle(self):
        if verbose:
            tStart=time.time()
        while self.check_write_busy():
            time.sleep(0.002)
        if verbose:
            print(f'wait_write_idle: waited for {time.time()-tStart} seconds')

    def read_id(self):
        answ=self.send_cmd(0x9F, data=20*bytes([0]))[1:] #or 0x09E, but xc3sprog uses 9F
        return {"ManufacturerID": answ[0:1],
                "MemoryType":     answ[1:2],
                "MemoryCapacity": answ[2:3],
                "UniqueID":       answ[3:]}
    
    def read_statusregister(self):
        return self.send_cmd(0x05, data=bytes([0]))[1]
    
    def read_flagstatusregister(self):
        if self.flashType in ("M25P", "IS25L"):
            return None
        else: #elif self.flashType=="N25Q":
            return self.send_cmd(0x70, data=bytes([0]))[1]
    
    def subsector_erase(self, address):
        if self.flashType=="N25Q":
            if verbose:
                print(f'Doing subsector erase({address=})')
            self.write_enable()
            self.send_cmd(0x20, address)
        else:
            pass

    def sector_erase(self, address):
        if verbose:
            print(f'Doing sector erase({address=})')
        self.write_enable()
        self.send_cmd(0xD8, address)
        
    def bulk_erase(self):
        if verbose:
            print(f'Doing a bulk-erase')
        self.write_enable()        
        self.send_cmd(0xC7)

    def page_program(self, address, data):
        self.write_enable()
        self.send_cmd(0x02, address=address, data=data)
        
    def read(self, address=0, ndata=None):
        if verbose: 
            print(f'read: {address=}, {ndata=}')
        data=bytes()
        endpos=address+ndata
        while len(data)<ndata:
            toread=min(2048, endpos-address)
            if debug:
                print(f'READ {address=}, {toread=}')
            data=data+bytes(self.send_cmd(0x03, address, toread*bytes([0]))[4:])
            address=len(data)
        return data

    def program(self, data):
        ndata=len(data)

        npages=-(-len(data)//self.pagelength)  #round up by taking negative twice:
        nsectors=-(-len(data)//self.sectorlength)
        for isector in range(nsectors):
            self.wait_write_idle()
            self.sector_erase(isector*self.sectorlength)

        print(f'Writing {npages} pages to flash')
            
        for ipage in range(npages):
            address=ipage*self.pagelength

            self.wait_write_idle()            

            self.page_program(address, data[address:address+self.pagelength])

            
    def program_filedata(self, filename):
        print(f'Programming flash with data from {filename}')
        
        with open(filename, 'rb') as f:
            data=f.read()
            
        self.program(data)
        self.check_file(filename)
            
    def read_tofile(self, filename):
        
        with open(filename, 'wb') as f:
            data=self.read(ndata=self.flashbits//8)
            f.write(data)
            
    def check_file(self, filename):
        print(f'Checking file: {filename}')
        with open(filename, 'rb') as f:
            filedata  = f.read()
            
        flashdata = self.read(ndata=len(filedata))
            
        if filedata==flashdata:
            print('Verify: PASS')
        else:
            errorPos=None
            for i, (f,d) in enumerate(zip(filedata, flashdata)):
                if f!=d:
                    errorPos=i
                    break
            print(f'Verify: ERROR. {len(filedata)=}, {len(flashdata)}, First error at position: {errorPos}')
            print(f'data starting at position {errorPos}:')
            print(f'filedata : {hexstr(filedata[errorPos:errorPos+16])}')
            print(f'flashdata: {hexstr(flashdata[errorPos:errorPos+16])}')

def hexstr(buf,addspace=8):
    #print(" ".join([f"{c:02x}" for c in buf[:16]]))
    s=""
    if addspace==0:
        addspace=len(buf)
    for i in range(-(-len(buf)//addspace)):
        s+=" ".join([f"{c:02x}" for c in buf[i*addspace:(i+1)*addspace]])
        s+="  "
        #print(f'---{s}-')
    return s.rstrip()
            
        
def main():
    global debug, verbose
    
    parser = argparse.ArgumentParser(
                    prog='flashcomm',
                    description='Program and read data from Flash chips')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--SPIdev', type=int, default=0, help="use SPIdev device number on SPI bus")
    parser.add_argument('--SPIspeed', type=int, help="use max SPI speed")
    parser.add_argument('--ss', type=int, help="Chip Select pin of Flash chip")    
    parser.add_argument('--getid', action='store_true', help="send the GET ID command, and print the results")
    parser.add_argument('--getstatus', action='store_true', help="read status register")
    parser.add_argument('--getflags', action='store_true', help="read flag status register")
    parser.add_argument('--program', help='program flash with contents of file')
    parser.add_argument('--verify', help='read contents of flash, and compare with contents of verify file')
    parser.add_argument('--save', help='save flash contents to file')
    parser.add_argument('--config', default='flashcomm.conf', help='use values in config file as defaults')

    args=parser.parse_args()

    if args.debug:
        debug=True
    if args.verbose:
        verbose=True
        
    spi_bus=0
    spi_device=0
    spi_ss=-1
    max_speed_hz=100000
    set_high=-1
    set_low=-1
    
    if args.config is not None:
        config=configparser.ConfigParser(inline_comment_prefixes=('#',))
        config.read(args.config)

        spi_bus=      config['SPI'].getint("bus",          spi_bus)
        spi_device=   config['SPI'].getint("device",       spi_device)
        spi_ss=       config['SPI'].getint(f"ss",          spi_ss)
        max_speed_hz= config['SPI'].getint("max_speed_hz", max_speed_hz)
        set_high=     config['SPI'].getint("set_high",     set_high)
        set_low =     config['SPI'].getint("set_low",      set_low)

    if args.SPIdev is not None:
        spi_device=args.SPIdev
    if args.ss is not None:
        spi_ss=args.SS
    if args.SPIspeed is not None:
        max_speed_hz=args.SPIspeed
    
    flash=flashcomm(device=spi_device, bus=spi_bus, max_speed_hz=max_speed_hz, ss=spi_ss, set_high=set_high, set_low=set_low)
    
    if args.getid:
        for k,v in flash.read_id().items():
            print(f'{k:15s}: {hexstr(v)}')

    if args.getstatus:
        status_register=flash.read_statusregister()
        print(f'Status Register: {hexstr(bytes([status_register]))}')
        
    if args.getflags:
        flags_register=flash.read_flagstatusregister()
        print(f'Flag status Register: {hexstr(bytes([flags_register]))}')
        
    if args.program is not None:
        flash.program_filedata(args.program)

    if args.verify is not None:
        flash.check_file(args.verify)
        
    if args.save is not None:
        flash.read_tofile(args.save)
        
if __name__=="__main__":
    main()
