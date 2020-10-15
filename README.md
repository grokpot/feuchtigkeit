## Flash the Pyboard
https://micropython.org/download/esp32/
## Rshell
https://github.com/dhylands/rshell
#### Connect rshell to ESP
`rshell -p /dev/cu.SLAB_USBtoUART`
#### List contents of ESP
(rshell) `ls -l /pyboard`
#### REPL via Rshell
(rshell) `repl`
(rshell) ctrl+x to exit
#### Edit main.py
(rshell) `edit /pyboard/main.py`
