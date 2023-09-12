Flashcomm: communicate with flash chips wired to a Rapsberry Pi over SPI

Status: Read/program flash works on one device

Program/read/verify flash chips
Get the flash ID


Example commands:

```
flashcomm --getid
flashcomm --program filename.bin
flashcomm --verify filename.bin
```

Currently, erasing happens via one 'bulk-erase' command. If the file to be saved in flash is a lot smaller than the flash itself, this is a *lot* slower than only erasing the area to be saved.