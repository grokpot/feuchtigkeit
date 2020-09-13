import network
import time
import ubinascii
import urequests as requests
from machine import ADC, Pin

# Sensitive
INFLUXDB_URL = 
INFLUXDB_TOKEN = 
WLAN_SSID = 
WLAN_PW = 

# Not sensitive
DEBUG = False
TEST = False
PIN_OUT = 32
PIN_IN = 34


def setup_network():
    """
    Connect to network
    Ideally this happens just once to reduce stress on network access point
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("connecting to network...")
        wlan.connect(WLAN_SSID, WLAN_PW)
        while not wlan.isconnected():
            pass
    device_ip = wlan.ifconfig()[0]
    if DEBUG:
        print("Device IP:", device_ip)
    # Convert mac address to human readable format
    return ubinascii.hexlify(wlan.config("mac"), ":").decode()


def setup_pins():
    """
    PIN_OUT so we can toggle power to ADC device
    PIN_IN to read ADC value
    """
    # Start accepting input from ADC device
    pin_in = Pin(PIN_IN, Pin.IN)
    adc = ADC(pin_in)
    # Calibrate ADC
    # set 11dB input attenuation (voltage range roughly 0.0v - 3.6v)
    adc.atten(ADC.ATTN_11DB)
    # set bit return values (returned range 0-4095)
    adc.width(ADC.WIDTH_12BIT)
    pin_out = Pin(PIN_OUT, Pin.OUT)
    return adc, pin_out


def _ss(data):
    """
    MicroPy doesn't have statistics library, so we need this
    Return sum of square deviations of sequence data.
    """
    c = sum(data) / len(data)
    ss = sum((x - c) ** 2 for x in data)
    return ss


def stdev(data, ddof=0):
    """
    MicroPy doesn't have statistics library, so we need this
    Calculates the population standard deviation by default; specify ddof=1 to compute the sample standard deviation.
    """
    n = len(data)
    if n < 2:
        raise ValueError("variance requires at least two data points")
    ss = _ss(data)
    pvar = ss / (n - ddof)
    return pvar ** 0.5


def test_sensor_reading(adc, pin_out):
    """
    Test how sensor values are affected by:
    1) Turning the sensor off (sleep after Pin off)
    2) Waiting before taking a reading (sleep after Pin on)
    Pin off s: 0 | Pin on s: 0 | Mean: 289 | Relative Stdev: 18
    Pin off s: 0.5 | Pin on s: 0 | Mean: 135 | Relative Stdev: 14
    Pin off s: 1 | Pin on s: 0 | Mean: 125 | Relative Stdev: 18
    Pin off s: 0 | Pin on s: 1 | Mean: 1716 | Relative Stdev: 6
    Pin off s: 0.5 | Pin on s: 1 | Mean: 2023 | Relative Stdev: 2
    Pin off s: 1 | Pin on s: 1 | Mean: 2023 | Relative Stdev: 0
    Pin off s: 0 | Pin on s: 2 | Mean: 2140 | Relative Stdev: 0
    Pin off s: 0.5 | Pin on s: 2 | Mean: 2160 | Relative Stdev: 0
    Pin off s: 1 | Pin on s: 2 | Mean: 2158 | Relative Stdev: 0
    Pin off s: 0 | Pin on s: 3 | Mean: 2175 | Relative Stdev: 0
    Pin off s: 0.5 | Pin on s: 3 | Mean: 2174 | Relative Stdev: 0
    Pin off s: 1 | Pin on s: 3 | Mean: 2169 | Relative Stdev: 0

    It looks like
    """
    sample_size = 20
    pin_off_seconds_list = [0, 0.5, 1]
    pin_on_seconds_list = [0, 1, 2, 3]

    def test_sensor(pin_on_seconds):
        for pin_off_seconds in pin_off_seconds_list:
            values_list = []
            for i in range(sample_size):
                pin_out.off()
                time.sleep(pin_off_seconds)
                pin_out.on()
                time.sleep(pin_on_seconds)
                values_list.append(adc.read())
            mean = int(sum(values_list) / len(values_list))
            print(
                "Pin off s:",
                pin_off_seconds,
                "| Pin on s:",
                pin_on_seconds,
                "| Mean:",
                mean,
                "| Relative Stdev:",
                int(stdev(values_list) * 100 / mean),
            )
            print()

    for pin_on_seconds in pin_on_seconds_list:
        test_sensor(pin_on_seconds)


def loop(mac_addr, adc, pin_out):
    """
    Turns on output pin
    Reads ADC Value
    POSTs to InfluxDB
    Turns off output (vcc) pin to avoid electrolysis
    Sleeps for
    """
    while True:
        # Turn output on so ADC device gets power
        pin_out.on()
        # Wait after turning pin on for accurate value
        time.sleep(2)
        adc_raw = adc.read()
        # Convert from 12 bit return values to scale of 0-100
        adc_percent = adc_raw * 100 / 4095
        # Inverse the value and convernt to int since the resting analog value is 100
        adc_percent = int(100 - adc_percent)
        response = requests.request(
            "POST",
            INFLUXDB_URL,
            data="feuchtigkeit,device_id={} adc_value={}".format(mac_addr, adc_percent),
            headers={"Authorization": "Token {}".format(INFLUXDB_TOKEN)},
        )
        if response.status_code != 204:
            raise Exception(
                "Bad response from InfluxDB: {}".format(response.status_code)
            )

        # Need to print these else the program fails with `mbedtls_ssl_handshake error: -4290`. No luck so far debugging it.
        print(response.status_code)
        print(response.content)

        pin_out.off()

        # Run every 15 mins
        time.sleep(60 * 15)


def main():
    mac_addr = setup_network()
    adc, pin_out = setup_pins()
    if TEST:
        test_sensor_reading(adc, pin_out)
    else:
        loop(mac_addr, adc, pin_out)


if __name__ == "__main__":
    main()
