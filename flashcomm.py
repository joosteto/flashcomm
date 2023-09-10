#!/usr/bin/python3
import argparse
import time


try:
    import spidev
except ModuleNotFoundError:
    print("No spidev module found, running in simulation mode")
    class spidev:
        class SpiDev:
            def __init__(self):
                pass
            def open(self, bus, device):
                self.bus=bus
                self.device=device
            def xfer2(self,data):
                return bytes([i%256 for i in [0,0]+list(range(len(data)))])
    


class flashcomm:
    def __init__(self, device=1, max_speed_hz=500000):
        #data about flash chip. Should be infered from device id
        self.pagelength=256
        self.flashbits=32*1024*1024

        #SPI location
        self.bus=0
        self.device=device
        self.spi=spidev.SpiDev()
        self.spi.open(self.bus, self.device)
        self.spi.max_speed_hz=max_speed_hz
        
        
    def send_cmd(self, cmd, address=None, data=None):
        """
        send_cmd: send command to Flash Device (over SPI)
        Arguments:
          cmd: command to send (integer)
          address: None, or address to send after command
          data: bytes to send after cmd+address (type: bytes)
        Return: data returend by Flash. 
        """
        if address is None:
            abytes=bytes([])
        else:
            abytes=address.to_bytes(3)
        if data is None:
            data=bytes([])
        return self.spi.xfer2(bytes([cmd])+abytes+data)
                                
    def write_enable(self):
        result=self.spi.xfer2(0x06)

    def read_statusregister(self):
        return self.send_cmd(0x05, data=bytes([0]))

    def check_write_busy(self):
        return self.read_statusregister()[1] & 1
    
    def wait_write_idle(self):
        while self.check_write_busy():
            time.sleep(0.001)

    def read_id(self):
        answ=self.send_cmd(0x9E, data=20*bytes([0]))[1:] #or 0x09F?
        return {"ManufacturerID": answ[0],
                "MemoryType":     answ[1],
                "MemoryCapacity": answ[2],
                "UniqueID":       answ[3:]}
    
    def bulk_erase(self):
        self.send_cmd(0xC7)

    def page_program(self, address, data):
        self.send_cmd(0x02, address)
        
    def read(self, address=0, ndata=None):
        return self.send_cmd(0x03, address, ndata*bytes([0]))[6:]

    def program(self, data):
        ndata=len(data)

        npages=-(-len(data)//self.pagelength)  #round up by taking negative twice:
        self.wait_write_idle()
        self.bulk_erase()
        
            
        for ipage in range(npages):
            address=ipage*self.pagelength

            self.wait_write_idle()            

            self.page_program(address, data[address:address+self.pagelength])
            
            
    def program_filedata(self, filename):
        with open(filename, 'rb') as f:
            data=f.read()
            self.program(data)
            
    def read_tofile(self, filename):
        with open(filename, 'wb') as f:
            data=self.read(ndata=self.flashbits//8)
            f.write(data)
            
    def check_file(self, filename):
        with open(filename, 'rb') as f:
            filedata  = f.read()
            flashdata = self.read(ndata=len(filedata))
            
        if filedata==flashdata:
            print('Verify: PASS')
        else:
            print(f'Verify: ERROR. {len(filedata)=}, {len(flashdata)}') 

            
        
def main():
    parser = argparse.ArgumentParser(
                    prog='flashcomm',
                    description='Program and read data from Flash chips')
    parser.add_argument('--SPIdev', type=int, default=0, help="use SPIdev device number on SPI bus")
    parser.add_argument('--SPIspeed', type=int, default=100000, help="use max SPI speed")
    parser.add_argument('--getid', action='store_true', help="send the GET ID command, and print the results")
    parser.add_argument('--program', help='program flash with contents of file')
    parser.add_argument('--verify', help='read contents of flash, and compare with contents of verify file')
    parser.add_argument('--save', help='save flash contents to file')

    args=parser.parse_args()

    SPIdev=args.SPIdev
    max_speed_hz=args.SPIspeed
    
    flash=flashcomm(device=SPIdev, max_speed_hz=max_speed_hz)
    
    if args.getid:
        for k,v in flash.read_id().items():
            print(f'{k:15s}: {v}')

    if args.program is not None:
        flash.program_filedata(args.program)

    if args.verify is not None:
        flash.check_file(args.verify)
        
    if args.save is not None:
        flash.read_tofile(args.save)
        
if __name__=="__main__":
    main()
