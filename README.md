Flashcomm: communicate with flash chips wired to a Rapsberry Pi over SPI.

Status: Read/program flash tested on N25Q032A, IS25LP064D and M25P10A flash chips.

Program/read/verify flash chips
Get the flash ID


Example commands:

```
flashcomm --getid
flashcomm --program filename.bin
flashcomm --verify filename.bin
```

To configure, use a flashcomm.conf file like this:
[SPI]
bus=0
device=0
max_speed_hz=1000000
ss=27        #Chip Select line of the Flash chip

#optional:
set_high=22  #This line is set high before (and during) programming (default: -1, don't use)
set_low=-1  #This line is set low before (and during) programming (default: -1, don't use)
